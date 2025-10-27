"""API Client for HVAC System."""
import logging
import aiohttp
import asyncio
from typing import Any
from bs4 import BeautifulSoup
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import re

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api.hvac-system.example.com"
API_LOGIN_ENDPOINT = "/api/login"
API_DATA_ENDPOINT = "/api/rooms/temperature"

class AuthenticationError(Exception):
    """Exception for authentication errors."""

class ConnectionError(Exception):
    """Exception for connection errors."""

class HVACApiClient:
    """API Client for HVAC System."""

    def __init__(self, username: str, password: str, hass) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.hass = hass
        self.session_id: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Use Home Assistant's async_get_clientsession helper to avoid blocking SSL calls
            # This helper handles SSL context creation in the executor to prevent blocking the event loop
            self._session = async_get_clientsession(self.hass, verify_ssl=False)
        return self._session
    
    async def _get_request(self, url: str) -> aiohttp.ClientResponse:
        """Make a GET request to the specified URL."""
        session = await self._get_session()
        try:
            async with session.get(
                url,
                headers={
                    "Cookie": f"PHPSESSID={self.session_id}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 401:
                    # Session expired, re-authenticate
                    _LOGGER.warning("Session expired, re-authenticating")
                    await self.authenticate()
                    # Retry the request after re-authentication
                    return await self._get_request(url)
                elif response.status != 200:
                    _LOGGER.error(f"API returned status: {response.status}")
                    raise ConnectionError(f"API returned status {response.status}")
                return await response.text()
        except asyncio.TimeoutError as e:
            raise ConnectionError(f"Timeout fetching URL: {url}") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Error fetching URL {url}: {e}") from e

    async def _post_request(self, url: str, data: Any) -> aiohttp.ClientResponse:
        """Make a POST request to the specified URL."""
        session = await self._get_session()
        try:
            async with session.post(
                url,
                headers={
                    "Cookie": f"PHPSESSID={self.session_id}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                },
                timeout=aiohttp.ClientTimeout(total=10),
                data=data
            ) as response:
                if response.status == 401:
                    # Session expired, re-authenticate
                    _LOGGER.info("Session expired, re-authenticating")
                    await self.authenticate()
                    # Retry the request after re-authentication
                    return await self._post_request(url, data)
                elif response.status != 200:
                    _LOGGER.error(f"API returned status: {response.status}")
                    raise ConnectionError(f"API returned status {response.status}")
                
                return response
        except asyncio.TimeoutError as e:
            raise ConnectionError(f"Timeout fetching URL: {url}") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Error fetching URL {url}: {e}") from e

    async def _fetch_and_parse_html(self, url: str) -> BeautifulSoup:
        """Fetch URL and return parsed BeautifulSoup object.
        
        Args:
            url: The URL to fetch
            
        Returns:
            BeautifulSoup object with parsed HTML content
            
        Raises:
            ConnectionError: If the request fails or returns non-200 status
        """
        try:
            html_content = await self._get_request(url)
            # Parse HTML response
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup
        except asyncio.TimeoutError as e:
            raise ConnectionError(f"Timeout fetching URL: {url}") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Error fetching URL {url}: {e}") from e

    async def authenticate(self) -> str:
        """Authenticate and get session ID."""
        session = await self._get_session()
        
        try:
            _LOGGER.debug(f"Logging in {self.username}")

            async with session.post(
                f"https://www.mywavinhome.com/login",
                data={
                    "username": self.username,
                    "password": self.password
                },
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                _LOGGER.debug("Response status: %s", response.status)
                if response.status == 401:
                    _LOGGER.error("Invalid username or password")
                    raise AuthenticationError("Invalid username or password")
                elif response.status != 200:
                    _LOGGER.error("Invalid username or password")
                    raise ConnectionError(f"API returned status {response.status}")
                
                # Extract session ID from Set-Cookie header
                set_cookie = response.headers.get("Set-Cookie", "")
                self.session_id = None
                _LOGGER.debug("Set-Cookie header: %s", set_cookie)
                # Parse session ID from cookie string (assuming format like "PHPSESSID=abc123; Path=/")
                if "PHPSESSID=" in set_cookie:
                    start = set_cookie.find("PHPSESSID=") + len("PHPSESSID=")
                    end = set_cookie.find(";", start)
                    if end == -1:
                        end = len(set_cookie)
                    self.session_id = set_cookie[start:end].strip()
                            # Extract PHPSESSID from cookie jar
                if not self.session_id:           
                    for cookie in session.cookie_jar:
                        if cookie.key == "PHPSESSID":
                            _LOGGER.info("Reused session id from cookie jar: %s", cookie.value)
                            self.session_id = cookie.value
                            break
            
                if not self.session_id:
                    _LOGGER.error("No session ID found in Set-Cookie header")
                    raise AuthenticationError("No session ID found in Set-Cookie header")
                _LOGGER.info("Session ID: %s", self.session_id)
                _LOGGER.info("Successfully authenticated with MyWavinHome Website")
                return self.session_id
                
        except asyncio.TimeoutError as e:
            _LOGGER.error("Timeout connecting to MyWavinHome Website: %s", e)
            raise ConnectionError("Timeout connecting to MyWavinHome Website") from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Error connecting to MyWavinHome Website: %s", e)
            raise ConnectionError(f"Error connecting to MyWavinHome Website: {e}") from e

    async def get_room_temperatures(self) -> dict[str, Any]:
        """Get temperature data for all rooms."""
        if not self.session_id:
            await self.authenticate()
        
        rooms = await self._fetch_and_parse_rooms(page_number=1)

        # Fetch target temperature for each room
        for room_id in rooms.keys():
            room_details = await self.get_room_details(room_id)
            rooms[room_id].update(room_details)
        return rooms

    async def get_room_details(self, room_id: str) -> dict[str, Any]:
        """Get room target temperature data."""
        if not self.session_id:
            await self.authenticate()

        details = {}
        soup = await self._fetch_and_parse_html(f"https://www.mywavinhome.com/settings/{room_id}")
        targetTemperature = soup.select_one('#myModeVal')

        if targetTemperature and targetTemperature.text:
            details["target_temperature"] = targetTemperature.text[:-2]
        heatingNode = soup.select_one('[src="/images/heat_1.png"]')

        if heatingNode:
            details["is_heating_on"] = True

        coolingNode = soup.select_one('[src="/images/cool_1.png"]')

        if coolingNode:
            details["is_cooling_on"] = True
        dayModeNode = soup.select_one('[src="/images/day_1.png"]')

        if dayModeNode:
            details["is_day_mode_on"] = True
        nightModeNode = soup.select_one('[src="/images/night_1.png"]')

        if nightModeNode:
            details["is_night_mode_on"] = True

        return details

    async def get_outside_temperature(self) -> str | None:
        """Get outside temperature data."""
        if not self.session_id:
            await self.authenticate()

        soup = await self._fetch_and_parse_html("https://www.mywavinhome.com/controls")
        outsideTemp = soup.select_one('[style="font-size:20px;color:red; font-weight:bold;"]')
        if outsideTemp and outsideTemp.text:
            return outsideTemp.text[:-2].replace("°C", "")
        _LOGGER.error("No outside temperature found in response")
        return None

    async def _fetch_and_parse_rooms(self, page_number: int) -> dict[str, Any]:
        """Parse room data from HTML content.
        
        Args:
            soup: The BeautifulSoup object with parsed HTML
            page_number: The page number being processed (for logging/debugging)
            
        Returns:
            Dictionary with room data keyed by room_id
        """
        try:
            soup = await self._fetch_and_parse_html(f"https://www.mywavinhome.com/thermostats?page={page_number}")

            # Extract data from XML - you'll need to adjust these selectors based on the actual HTML structure
            rooms = {}
            for room in soup.select(".items .listview"):
                room_name = room.select_one('.thermoInput').get('value', '')
                temperature: str = None
                humidity: str = None
                id_attribute_link = room.select_one('.thermHeader a').get('href', '')
                # Extract room ID from link like "settings/9130575" -> "9130575"
                room_id = id_attribute_link.split('/')[-1] if '/' in id_attribute_link else id_attribute_link
                for thermData in room.select(".thermHeader2"):
                    text: str = thermData.text
                    if text.endswith(" rh%"):
                        humidity = text[:-4]
                    elif text.endswith("°C"):
                        temperature = text[:-2]
                _LOGGER.info(f"Room details (page {page_number}, room {room_id}): {room_name}, {temperature}, {humidity}")

                rooms[room_id] = {"name": room_name, "temperature": temperature.strip(), "humidity": humidity.strip()}

            # Check for next page AFTER processing all rooms on current page
            if soup.select_one('.next:not(.hidden)'):
                # There is a next page, fetch and parse it recursively
                next_page_rooms = await self._fetch_and_parse_rooms(page_number + 1)
                rooms.update(next_page_rooms)
            return rooms
        except Exception as e:
            _LOGGER.error(f"Error processing HTML (page {page_number}): {e}")
            raise ConnectionError(f"Error processing response (page {page_number}): {e}")

    async def close(self) -> None:
        """Close the API session."""
        # When using Home Assistant's async_get_clientsession, we don't need to close the session
        # as it's managed by Home Assistant itself
        self._session = None

    async def set_room_target_temperature(self, room_id: str, target_temperature: float) -> None:
        """Set target temperature for a room.
        
        Args:
            room_id: The ID of the room
            target_temperature: The desired target temperature
        """
        if not self.session_id:
            await self.authenticate()

        soup = await self._fetch_and_parse_html(f"https://www.mywavinhome.com/settings/{room_id}")
        current_target_temperature_node = soup.select_one('#myModeVal')
        current_target_temperature = float(current_target_temperature_node.text[:-2])
        temperature_difference = current_target_temperature - target_temperature

        if temperature_difference == 0:
            _LOGGER.warning(f"Target temperature for room {room_id} is already {target_temperature}°C, no update needed.")
            return
        
        temperature_selector_buttons = soup.select('#thermostatBG div[onclick]')
        script_tag = soup.select_one('#thermostatBG script')
        _LOGGER.warning(f"Script tag content: {script_tag.string if script_tag else 'None'}")
        if not script_tag or not script_tag.string:
            _LOGGER.warning(f"No script tag found for room {room_id}.")
            return
        matched_element_id = re.search(r"\$\('#([a-zA-Z0-9]*)'\)", script_tag.string if script_tag else '')
        if not matched_element_id:
            _LOGGER.warning(f"No matched element ID found for room {room_id}.")
            return
        if not temperature_selector_buttons:
            _LOGGER.warning(f"No temperature selector buttons found for room {room_id}. No elements matched.")
            return
        # throw an exception if the temperature_selector_buttons array is empty
        if len(temperature_selector_buttons) == 0:
            _LOGGER.warning(f"No temperature selector buttons found for room {room_id}. Empty array.")
            return
        
        # Debug: Log all style attributes to see what we're working with
        _LOGGER.info(f"Found {len(temperature_selector_buttons)} temperature selector buttons for room {room_id}")
        for i, selector in enumerate(temperature_selector_buttons):
            id_attribute = selector.attrs.get("id", "")
            _LOGGER.error(f"Button {i} id: '{id_attribute}' (type: {type(id_attribute)})")

        current_target_temperature_selector_index = next(
            (
                i
                for i, selector in enumerate(temperature_selector_buttons)
                if matched_element_id and matched_element_id.group(1) == selector.attrs.get("id", "")
            ),
            None,
        )
        if current_target_temperature_selector_index is None:
            _LOGGER.warning(f"Could not find temperature selector buttons for room {room_id}")
            return
        _LOGGER.error(f"Current target temperature selector index for room {room_id}: {current_target_temperature_selector_index}, ({temperature_selector_buttons[current_target_temperature_selector_index].attrs.get('id', '') if current_target_temperature_selector_index is not None else 'N/A'})")
        new_target_temperature_selector_index = current_target_temperature_selector_index - int(temperature_difference)
        if new_target_temperature_selector_index < 0 or new_target_temperature_selector_index >= len(temperature_selector_buttons):
            _LOGGER.warning(f"Calculated selector index {new_target_temperature_selector_index} is out of bounds for room {room_id}")
            return
        _LOGGER.error(f"New target temperature selector index for room {room_id}: {new_target_temperature_selector_index}, ({temperature_selector_buttons[new_target_temperature_selector_index].attrs.get('id', '') if current_target_temperature_selector_index is not None else 'N/A'})")

        target_selector_button = temperature_selector_buttons[new_target_temperature_selector_index]
        # The expected content is `javascript:setTemperature(1,995045,0);`
        # We need to extract the parameters from this string to make the API call
        js_content = target_selector_button.get("onclick", "")
        if not js_content.startswith("javascript:setTemperature"):
            _LOGGER.warning(f"Unexpected javascript content for temperature selector button: {js_content}")
            return
        
        params_start = js_content.find("(") + 1
        params_end = js_content.find(")")
        params = js_content[params_start:params_end].split(",")
        if len(params) != 3:
            _LOGGER.warning(f"Unexpected number of parameters in javascript content: {js_content}")
            return
        # Prepare and send the API request to set the temperature
        param_temperature_value = params[1]
        param_room_id = params[0]
        _LOGGER.warning(f"Setting target temperature for room {room_id} to {target_temperature}°C using parameters: id={param_room_id}, value={param_temperature_value}")
        await self._post_request(
            "https://www.mywavinhome.com/settemperature",
            data={
                "id": room_id,
                "value": param_temperature_value
            }
        )
