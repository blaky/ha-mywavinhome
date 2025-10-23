"""API Client for HVAC System."""
import logging
import aiohttp
import asyncio
from typing import Any
from bs4 import BeautifulSoup
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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

    async def authenticate(self) -> str:
        """Authenticate and get session ID."""
        session = await self._get_session()
        
        try:
            _LOGGER.error(f"Logging in {self.username}")

            async with session.post(
                f"https://www.mywavinhome.com/login",
                data={
                    "username": self.username,
                    "password": self.password
                },
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                _LOGGER.error("Response status: %s", response.status)
                if response.status == 401:
                    _LOGGER.error("Invalid username or password")
                    raise AuthenticationError("Invalid username or password")
                elif response.status != 200:
                    _LOGGER.error("Invalid username or password")
                    raise ConnectionError(f"API returned status {response.status}")
                
                # Extract session ID from Set-Cookie header
                set_cookie = response.headers.get("Set-Cookie", "")
                self.session_id = None
                _LOGGER.error("Set-Cookie header: %s", set_cookie)
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
        
        return await self._fetch_and_parse_rooms(page_number=1)

    async def get_outside_temperature(self) -> str | None:
        """Get outside temperature data."""
        if not self.session_id:
            await self.authenticate()

        session = await self._get_session()
        
        try:
            async with session.get(
                f"https://www.mywavinhome.com/controls",
                headers={"Cookie": f"PHPSESSID={self.session_id}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 401:
                    # Session expired, re-authenticate
                    _LOGGER.error("Session expired, re-authenticating")
                    await self.authenticate()
                    return await self.get_outside_temperature()
                elif response.status != 200:
                    _LOGGER.error(f"API returned status: {response.status}")
                    raise ConnectionError(f"API returned status {response.status}")
                
                # Parse HTML response
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                outsideTemp = soup.select_one('[style="font-size:20px;color:red; font-weight:bold;"]')
                if outsideTemp and outsideTemp.text:
                    return outsideTemp.text[:-2].replace("°C", "")
                _LOGGER.error("No outside temperature found in response")
                _LOGGER.error(html_content)
                return None
        except asyncio.TimeoutError as e:
            raise ConnectionError("Timeout fetching temperature data") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Error fetching temperature data: {e}") from e

    async def _fetch_and_parse_rooms(self, page_number: int) -> dict[str, Any]:
        """Fetch and parse room data from thermostats page.
        
        Args:
            page_number: The page number being processed (for logging/debugging)
            
        Returns:
            Dictionary with room data keyed by room_id
        """
        session = await self._get_session()
        
        try:
            async with session.get(
                f"https://www.mywavinhome.com/thermostats?page={page_number}",
                headers={"Cookie": f"PHPSESSID={self.session_id}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 401:
                    # Session expired, re-authenticate
                    _LOGGER.error("Session expired, re-authenticating")
                    await self.authenticate()
                    return await self._fetch_and_parse_rooms(page_number)
                elif response.status != 200:
                    _LOGGER.error(f"API returned status: {response.status}")
                    raise ConnectionError(f"API returned status {response.status}")
                
                # Parse HTML response
                html_content = await response.text()
                return await self._parse_rooms_from_html(html_content, page_number)
                
        except asyncio.TimeoutError as e:
            raise ConnectionError("Timeout fetching temperature data") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Error fetching temperature data: {e}") from e

    async def _parse_rooms_from_html(self, html_content: str, page_number: int) -> dict[str, Any]:
        """Parse room data from HTML content.
        
        Args:
            html_content: The HTML content to parse
            page_number: The page number being processed (for logging/debugging)
            
        Returns:
            Dictionary with room data keyed by room_id
        """
        try:
            # Parse as XML/HTML
            
            # Extract data from XML - you'll need to adjust these selectors based on the actual HTML structure
            rooms = {}
            soup = BeautifulSoup(html_content, 'html.parser')
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
