"""Config flow for WaterSmart integration."""

from asyncio import timeout
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .client import AuthenticationError, WaterSmartClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Args:
        hass: The Home Assistant instance.
        data: The user input to validate.

    Raises:
        CannotConnect: If the connection to WaterSmart failed.
        InvalidAuth: If the credentials are invalid.
    """

    session = async_get_clientsession(hass)
    client = WaterSmartClient(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], session=session
    )

    try:
        async with timeout(30):
            account_number = await client.async_get_account_number()
    except (ClientConnectorError, TimeoutError, ClientError) as error:
        raise CannotConnect from error
    except AuthenticationError as error:
        raise InvalidAuth from error

    if not account_number:
        raise InvalidAuth


class WaterSmartConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for WaterSmart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        Returns:
            The config flow result.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_check_credentials(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]} ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "example_host": "bendoregon",
                "example_url": "https://bendoregon.watersmart.com/",
            },
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle a reauth flow when the stored credentials stop working.

        Returns:
            The config flow result.
        """

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth confirmation step.

        Returns:
            The config flow result.
        """
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**entry.data, **user_input}
            errors = await self._async_check_credentials(candidate)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=candidate)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration step.

        Returns:
            The config flow result.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_check_credentials(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, entry.data
            ),
            errors=errors,
        )

    async def _async_check_credentials(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate credentials, returning form errors when they fail.

        Returns:
            Form errors, or an empty dict when the credentials are valid.
        """
        try:
            await validate_input(self.hass, data)
        except CannotConnect:
            return {"base": "cannot_connect"}
        except InvalidAuth:
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
