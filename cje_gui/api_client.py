import requests
from typing import Any, Optional

from config import get_setting


class AuthenticationError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or get_setting("api", "url")).rstrip("/")
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None

    # ── Autenticación ──────────────────────────────────────
    def login(self, username: str, password: str) -> None:
        r = self.session.post(
            f"{self.base_url}/token/",
            data={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code != 200:
            raise AuthenticationError("Usuario o contraseña incorrectos")
        self.access_token = r.json()["access_token"]
        self._username = username
        self._password = password
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def logout(self) -> None:
        self.access_token = None
        self._username = None
        self._password = None
        self.session.headers.pop("Authorization", None)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 401 and self._username is not None:
            try:
                self.login(self._username, self._password)
            except AuthenticationError:
                pass
            resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Fletes ────────────────────────────────────────────
    def get_fletes(self) -> list[dict[str, Any]]:
        r = self._request("GET", f"{self.base_url}/fletes")
        return r.json()

    def create_flete(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/fletes/", json=data)
        return r.json()

    def update_flete(self, id_flete: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/fletes/{id_flete}", json=data)
        return r.json()

    def delete_flete(self, id_flete: int) -> None:
        self._request("DELETE", f"{self.base_url}/fletes/{id_flete}")

    # ── Clientes ──────────────────────────────────────────
    def get_clientes(self) -> list[dict[str, Any]]:
        r = self._request("GET", f"{self.base_url}/clientes")
        return r.json()

    def get_cliente(self, cedula: int) -> dict[str, Any]:
        r = self._request("GET", f"{self.base_url}/clientes/{cedula}")
        return r.json()

    def create_cliente(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/clientes/", json=data)
        return r.json()

    def update_cliente(self, cedula: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/clientes/{cedula}", json=data)
        return r.json()

    def delete_cliente(self, cedula: int) -> None:
        self._request("DELETE", f"{self.base_url}/clientes/{cedula}")

    # ── Catálogo ──────────────────────────────────────────
    def get_catalogo(self) -> list[dict[str, Any]]:
        r = self._request("GET", f"{self.base_url}/catalogo")
        return r.json()

    def create_catalogo(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/catalogo/", json=data)
        return r.json()

    def update_catalogo(self, id_catalogo: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/catalogo/{id_catalogo}", json=data)
        return r.json()

    def delete_catalogo(self, id_catalogo: int) -> None:
        self._request("DELETE", f"{self.base_url}/catalogo/{id_catalogo}")

    # ── Inventario ────────────────────────────────────────
    def get_inventario(self) -> list[dict[str, Any]]:
        r = self._request("GET", f"{self.base_url}/inventario")
        return r.json()

    def create_inventario(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/inventario/", json=data)
        return r.json()

    def update_inventario(self, id_inventario: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/inventario/{id_inventario}", json=data)
        return r.json()

    def delete_inventario(self, id_inventario: int) -> None:
        self._request("DELETE", f"{self.base_url}/inventario/{id_inventario}")

    # ── Ventas ─────────────────────────────────────────────
    def get_ventas(self, cedula: int = None) -> list[dict[str, Any]]:
        url = f"{self.base_url}/ventas"
        if cedula is not None:
            url += f"?cedula={cedula}"
        r = self._request("GET", url)
        return r.json()

    def get_venta(self, id_venta: int) -> dict[str, Any]:
        r = self._request("GET", f"{self.base_url}/ventas/{id_venta}")
        return r.json()

    def create_venta(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/ventas/", json=data)
        return r.json()

    def update_venta(self, id_venta: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/ventas/{id_venta}", json=data)
        return r.json()

    def delete_venta(self, id_venta: int) -> None:
        self._request("DELETE", f"{self.base_url}/ventas/{id_venta}")

    # ── Abonos ─────────────────────────────────────────────
    def get_abonos(self, cedula: int = None) -> list[dict[str, Any]]:
        url = f"{self.base_url}/abonos"
        if cedula is not None:
            url += f"?cedula={cedula}"
        r = self._request("GET", url)
        return r.json()

    def create_abono(self, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("POST", f"{self.base_url}/abonos/", json=data)
        return r.json()

    def update_abono(self, id_abono: int, data: dict[str, Any]) -> dict[str, Any]:
        r = self._request("PUT", f"{self.base_url}/abonos/{id_abono}", json=data)
        return r.json()

    def delete_abono(self, id_abono: int) -> None:
        self._request("DELETE", f"{self.base_url}/abonos/{id_abono}")
