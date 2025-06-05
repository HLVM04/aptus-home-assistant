"""AptusPortal API Client for Home Assistant integration."""

import json
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class AptusError(Exception):
    """Base class for all AptusPortal-related exceptions."""


class AptusLoginError(AptusError):
    """Raised when login to the AptusPortal fails due to incorrect credentials."""


class AptusNotLoggedInError(AptusError):
    """Raised when an operation requires login but the user is not logged in."""


class AptusAPIError(AptusError):
    """Raised when the AptusPortal API returns an error response."""

    def __init__(
        self,
        message: str,
        http_code: int | None = None,
        api_message: str | None = None,
        status_text: str | None = None,
    ) -> None:
        """Initialize with an error message, HTTP code, API message, and status text."""
        super().__init__(message)
        self.http_code = http_code
        self.api_message = api_message
        self.status_text = status_text


class AptusDependencyError(AptusError):
    """Raised when a required dependency for the AptusPortal client is not installed."""


class AptusClient:
    """A Python client to interact with the AptusPortal API."""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the AptusClient with base URL, username, and password."""
        self.base_url: str = base_url
        self.session: requests.Session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 "
                "Safari/537.36.",
            }
        )
        self.username: str | None = username
        self.password: str | None = password
        self._logged_in: bool = False
        self._request_verification_token: str | None = None
        self._password_salt: str | None = None

    def _make_url(self, endpoint: str) -> str:
        return urljoin(self.base_url, endpoint)

    def _encrypt_password(self, password_str: str, salt_str: str | None) -> str:
        """Replicates the XOR encryption logic from pwEnc.js."""
        if not salt_str:
            salt_str = "611"

        try:
            key = int(salt_str)
        except ValueError:
            key = 611

        encrypted_chars = []
        for char_in_password in password_str:
            char_code = ord(char_in_password)
            encrypted_char_code = key ^ char_code
            encrypted_chars.append(chr(encrypted_char_code))

        return "".join(encrypted_chars)

    def _get_login_page_details(self) -> bool:
        login_page_url = self._make_url("Account/Login")

        fetch_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            response = self.session.get(
                login_page_url, timeout=20, headers=fetch_headers, allow_redirects=True
            )

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            if token_input and token_input.get("value"):  # type: ignore  # noqa: PGH003
                self._request_verification_token = token_input["value"]  # type: ignore  # noqa: PGH003
            else:
                return False

            salt_input = soup.find(
                "input", {"id": "PasswordSalt", "name": "PasswordSalt"}
            )
            if salt_input and salt_input.get("value"):  # type: ignore  # noqa: PGH003
                self._password_salt = salt_input["value"]  # type: ignore  # noqa: PGH003
            else:
                self._password_salt = "611"  # noqa: S105

            return True  # noqa: TRY300

        except requests.exceptions.TooManyRedirects:
            return False
        except requests.exceptions.HTTPError:
            return False
        except requests.exceptions.RequestException:
            return False

    def login(self, username: str | None = None, password: str | None = None) -> bool:
        """Login to the AptusPortal with provided username and password."""
        if username:
            self.username = username
        if password:
            self.password = password

        if not self.username or not self.password:
            return False

        if not self._get_login_page_details():
            return False

        if not self._request_verification_token or not self._password_salt:
            return False

        encrypted_password = self._encrypt_password(self.password, self._password_salt)

        login_endpoint = "Account/Login"
        login_url_params = {"ReturnUrl": "/AptusPortal/"}

        payload = {
            "__RequestVerificationToken": self._request_verification_token,
            "DeviceType": "PC",
            "DesktopSelected": "true",
            "UserName": self.username,
            "Password": "",
            "PwEnc": encrypted_password,
            "PasswordSalt": self._password_salt,
        }

        post_headers = dict(self.session.headers)
        post_headers.pop("X-Requested-With", None)
        post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        post_headers["Referer"] = self._make_url("Account/Login")

        try:
            response = self.session.post(
                self._make_url(login_endpoint),
                params=login_url_params,
                data=payload,
                headers=post_headers,
                timeout=15,
                allow_redirects=True,
            )
            response.raise_for_status()

            if "Account/Login" in response.url:
                self._logged_in = False
                return False

            if (
                "Log ud" in response.text
                or "L&#229;s" in response.text
                or "Lås" in response.text
            ):
                self._logged_in = True
                self.session.headers["X-Requested-With"] = "XMLHttpRequest"
                return True
            self._logged_in = False
            return False  # noqa: TRY300

        except requests.exceptions.HTTPError:
            self._logged_in = False
            return False
        except requests.exceptions.RequestException:
            self._logged_in = False
            return False

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        expect_json: bool = True,  # noqa: FBT001, FBT002
    ) -> dict[str, Any] | str:
        if not self._logged_in and not endpoint.startswith("Account/Login"):
            return {"error": "NotLoggedIn", "message": "User is not logged in."}

        url = self._make_url(endpoint)

        current_headers = dict(self.session.headers)
        current_headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            response = self.session.request(
                method,
                url,
                params=params,
                data=data,
                headers=current_headers,
                timeout=15,
            )
            response.raise_for_status()

            if expect_json:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"raw_text": response.text, "error": "JSONDecodeError"}
            else:
                return response.text
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                msg = error_data.get("errorMessage", e.response.text)
                header_status = error_data.get("HeaderStatusText", "")
                return {  # noqa: TRY300
                    "error": "APIError",
                    "message": msg,
                    "status_text": header_status,
                    "http_code": e.response.status_code,
                }
            except (json.JSONDecodeError, AttributeError):
                return {
                    "error": "HTTPError",
                    "message": str(e),
                    "raw_response": e.response.text if e.response else None,
                    "http_code": e.response.status_code if e.response else None,
                }
        except requests.exceptions.RequestException as e:
            return {"error": "RequestException", "message": str(e)}

    def logout(self) -> str | None:
        """Logout from the AptusPortal."""
        logout_url = self._make_url("Account/LogOff")

        logout_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": self._make_url("Lock"),
        }

        try:
            response = self.session.get(
                logout_url, headers=logout_headers, timeout=20, allow_redirects=True
            )
            response.raise_for_status()

            self._logged_in = False
            self._request_verification_token = None
            self._password_salt = None

            return response.text if hasattr(response, "text") else None

        except (
            requests.exceptions.TooManyRedirects,
            requests.exceptions.HTTPError,
            requests.exceptions.RequestException,
            Exception,
        ):
            self._logged_in = False
            self._request_verification_token = None
            self._password_salt = None
            return None

    def set_lock_status_temp_data(self) -> str:
        """Set temporary data for lock status."""
        result = self._request("GET", "Lock/SetLockStatusTempData", expect_json=False)
        return result if isinstance(result, str) else ""

    def get_doorman_lock_status(self) -> dict[str, Any] | None:
        """Get the status of the doorman lock."""
        if not self._logged_in:
            return None
        self.set_lock_status_temp_data()
        result = self._request("GET", "LockAsync/DoormanLockStatus")
        return result if isinstance(result, dict) else None

    def poll_ongoing_call(self) -> dict[str, Any]:
        """Poll for ongoing call status."""
        result = self._request("GET", "Lock/PollOngingCall")
        return result if isinstance(result, dict) else {}

    def unlock_entrance_door(self, lock_id: int) -> dict[str, Any]:
        """Unlock the entrance door with the given lock ID."""
        try:
            result = self._request("GET", f"Lock/UnlockEntryDoor/{lock_id}")
        except Exception:  # noqa: BLE001
            # Login and retry on exception
            self.login(self.username, self.password)
            result = self._request("GET", f"Lock/UnlockEntryDoor/{lock_id}")

        return result if isinstance(result, dict) else {}

    def lock_doorman_lock(self) -> dict[str, Any]:
        """Lock the doorman lock."""
        result = self._request("GET", "Lock/LockDoormanLock")
        return result if isinstance(result, dict) else {}

    def unlock_doorman_lock(self, code: str) -> dict[str, Any]:
        """Unlock the doorman lock with the given code."""
        result = self._request("GET", "Lock/UnlockDoormanLock", params={"code": code})
        return result if isinstance(result, dict) else {}

    def list_available_locks(self) -> list[dict[str, int | str]] | None:
        """List all available entrance locks."""
        if not self._logged_in:
            return None

        original_xrw = self.session.headers.pop("X-Requested-With", None)
        response_text = self.session.get(self._make_url("Lock")).text
        if original_xrw:
            self.session.headers["X-Requested-With"] = original_xrw

        soup = BeautifulSoup(response_text, "html.parser")
        lock_cards = soup.find_all("div", class_="lockCard")
        available_locks: list[dict[str, int | str]] = []
        for card in lock_cards:
            if card.get("id", "").startswith("entranceDoor_"):  # type: ignore  # noqa: PGH003
                lock_id_str = card["id"].split("_")[-1]  # type: ignore  # noqa: PGH003
                try:
                    lock_id = int(lock_id_str)
                    name_div = card.find("div")  # type: ignore  # noqa: PGH003
                    main_name = name_div.contents[0].strip()  # type: ignore  # noqa: PGH003
                    sub_name_span = name_div.find("span")  # type: ignore  # noqa: PGH003
                    sub_name = sub_name_span.text.strip() if sub_name_span else ""  # type: ignore  # noqa: PGH003
                    full_name = f"{main_name} ({sub_name})" if sub_name else main_name
                    available_locks.append(
                        {"id": lock_id, "name": full_name, "raw_id_attr": card["id"]}  # type: ignore  # noqa: PGH003
                    )
                except ValueError:
                    continue
        return available_locks


# if __name__ == "__main__":
#     if not BeautifulSoup:
#         print(
#             "This script requires BeautifulSoup4 for parsing HTML"
#             "(e.g., login page, lock list)."
#         )
#         print("Please install it: pip install beautifulsoup4")
#         exit()

#     # Example usage - replace with your actual credentials
#     APTUS_USERNAME = ""
#     APTUS_PASSWORD = ""
#     APTUS_BASE_URL = ""

#     client = AptusClient(base_url=APTUS_BASE_URL)

#     print("--- Attempting Login ---")
#     if client.login(APTUS_USERNAME, APTUS_PASSWORD):
#         print("\nLOGIN SUCCEEDED (according to client logic)")

#         if BeautifulSoup:
#             print("\n--- Listing Available Entrance Locks ---")
#             locks = client.list_available_locks()
#             if isinstance(locks, list) and locks:
#                 for lock in locks:
#                     print(f"  ID: {lock['id']}, Name: {lock['name']}")
#             elif isinstance(locks, str):
#                 print(locks)
#             else:
#                 print("  No entrance locks found or error during listing.")
#         else:
#             print("\n--- Skipping lock listing (BeautifulSoup4 not installed) ---")

#         print("\n--- Logging Out ---")
#         client.logout()
#     else:
#         print("\nLOGIN FAILED")
#         print("Please check your credentials and review any error messages.")
