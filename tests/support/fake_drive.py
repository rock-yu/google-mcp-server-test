from __future__ import annotations

import base64
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace

from googleapiclient.errors import HttpError

DATASET_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "drive_dataset.json"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"


class FakeResponse(dict):
    def __init__(self, status: int, **headers):
        super().__init__(headers)
        self.status = status
        self.reason = headers.get("reason", "")


def _http_error(status: int, reason: str, uri: str = "fake://drive") -> HttpError:
    content = json.dumps(
        {"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}}
    ).encode()
    return HttpError(FakeResponse(status, reason=reason), content, uri=uri)


def load_dataset(path: Path = DATASET_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(data)
    return data


def validate_dataset(data: dict) -> None:
    required = {
        "id",
        "name",
        "mimeType",
        "createdTime",
        "modifiedTime",
        "owners",
        "trashed",
        "sharedWithMe",
    }
    if not isinstance(data.get("files"), list) or not data["files"]:
        raise ValueError("dataset.files must be a non-empty list")
    ids: set[str] = set()
    for index, file in enumerate(data["files"]):
        missing = required - file.keys()
        if missing:
            raise ValueError(f"dataset file {index} lacks: {', '.join(sorted(missing))}")
        if file["id"] in ids:
            raise ValueError(f"duplicate file id: {file['id']}")
        ids.add(file["id"])
        if not isinstance(file["owners"], list):
            raise ValueError(f"owners must be a list for {file['id']}")
    for file_id, permissions in data.get("permissions", {}).items():
        if file_id not in ids or not isinstance(permissions, list):
            raise ValueError(f"invalid permissions fixture for {file_id}")
    failures = data.get("failures", {})
    for name in ("inaccessible", "missing"):
        if name not in failures or not isinstance(failures[name].get("status"), int):
            raise ValueError(f"missing failure fixture: {name}")


class FakeRequest:
    def __init__(self, result=None, error: HttpError | None = None):
        self._result = result
        self._error = error

    def execute(self):
        if self._error:
            raise self._error
        return copy.deepcopy(self._result)


class FakeMediaHttp:
    def __init__(self, content: bytes):
        self.content = content

    def request(self, uri, method, body=None, headers=None, **kwargs):
        match = re.match(r"bytes=(\d+)-(\d+)", (headers or {}).get("range", ""))
        start = int(match.group(1)) if match else 0
        end = min(int(match.group(2)) + 1, len(self.content)) if match else len(self.content)
        chunk = self.content[start:end]
        return (
            FakeResponse(
                206,
                **{
                    "content-range": f"bytes {start}-{max(start, end - 1)}/{len(self.content)}",
                    "content-length": str(len(chunk)),
                },
            ),
            chunk,
        )


class FakeMediaRequest:
    def __init__(self, file_id: str, content: bytes):
        self.uri = f"fake://drive/files/{file_id}?alt=media"
        self.headers = {}
        self.http = FakeMediaHttp(content)


class _QueryParser:
    TOKEN = re.compile(
        r"\s*(?:(and|or|not)\b|(\()|(\))|"
        r"('(?:\\.|[^'])*'\s+in\s+(?:parents|owners))|"
        r"(sharedWithMe\b)|"
        r"((?:name|fullText|mimeType|modifiedTime|createdTime|viewedByMeTime|trashed)"
        r"\s*(?:contains|=|!=|<=|>=|<|>)\s*(?:'(?:\\.|[^'])*'|true|false)))",
        re.IGNORECASE,
    )

    def __init__(self, query: str):
        self.tokens: list[str] = []
        position = 0
        while position < len(query):
            match = self.TOKEN.match(query, position)
            if not match:
                raise ValueError(f"unsupported fake Drive query near: {query[position:]}")
            self.tokens.append(next(value for value in match.groups() if value is not None))
            position = match.end()
        self.index = 0

    def evaluate(self, file: dict) -> bool:
        self.index = 0
        result = self._or(file)
        if self.index != len(self.tokens):
            raise ValueError("unexpected query tokens")
        return result

    def _or(self, file: dict) -> bool:
        result = self._and(file)
        while self._accept("or"):
            result = self._and(file) or result
        return result

    def _and(self, file: dict) -> bool:
        result = self._factor(file)
        while self._accept("and"):
            result = self._factor(file) and result
        return result

    def _factor(self, file: dict) -> bool:
        if self._accept("not"):
            return not self._factor(file)
        if self._accept("("):
            result = self._or(file)
            self._expect(")")
            return result
        token = self.tokens[self.index]
        self.index += 1
        return self._predicate(token, file)

    def _accept(self, value: str) -> bool:
        if self.index < len(self.tokens) and self.tokens[self.index].lower() == value:
            self.index += 1
            return True
        return False

    def _expect(self, value: str) -> None:
        if not self._accept(value):
            raise ValueError(f"expected {value}")

    @staticmethod
    def _unquote(value: str) -> str:
        return value[1:-1].replace("\\'", "'").replace("\\\\", "\\")

    def _predicate(self, token: str, file: dict) -> bool:
        if token.lower() == "sharedwithme":
            return bool(file.get("sharedWithMe"))
        membership = re.fullmatch(r"('(?:\\.|[^'])*')\s+in\s+(parents|owners)", token, re.I)
        if membership:
            value = self._unquote(membership.group(1))
            field = membership.group(2).lower()
            values = file.get("parents", []) if field == "parents" else [
                owner.get("emailAddress") for owner in file.get("owners", [])
            ]
            return value in values or (field == "owners" and value == "me" and "me@example.test" in values)
        comparison = re.fullmatch(
            r"(\w+)\s*(contains|=|!=|<=|>=|<|>)\s*('(?:\\.|[^'])*'|true|false)",
            token,
            re.I,
        )
        if not comparison:
            raise ValueError(f"unsupported predicate: {token}")
        field, operator, raw_value = comparison.groups()
        expected = (
            raw_value.lower() == "true"
            if raw_value.lower() in ("true", "false")
            else self._unquote(raw_value)
        )
        if field == "fullText":
            actual = " ".join(
                str(file.get(key, "")) for key in ("name", "description", "content", "exportContent")
            )
        else:
            actual = file.get(field)
        if operator.lower() == "contains":
            return str(expected).lower() in str(actual or "").lower()
        operations = {
            "=": lambda: actual == expected,
            "!=": lambda: actual != expected,
            "<": lambda: actual is not None and actual < expected,
            ">": lambda: actual is not None and actual > expected,
            "<=": lambda: actual is not None and actual <= expected,
            ">=": lambda: actual is not None and actual >= expected,
        }
        return operations[operator]()


class FakeFilesResource:
    def __init__(self, backend: "FakeDriveService"):
        self.backend = backend

    def _file(self, file_id: str) -> dict:
        failure = self.backend.failures.get(file_id)
        if failure:
            raise _http_error(failure["status"], failure["reason"])
        try:
            return self.backend.records[file_id]
        except KeyError:
            raise _http_error(404, "notFound") from None

    def list(self, **kwargs):
        try:
            files = [
                file for file in self.backend.records.values()
                if _QueryParser(kwargs.get("q", "trashed = false")).evaluate(file)
            ]
            order = kwargs.get("orderBy")
            if order:
                field = order.split()[0]
                if field == "recency":
                    key = lambda item: max(
                        item.get("viewedByMeTime", ""),
                        item.get("modifiedTime", ""),
                        item.get("createdTime", ""),
                    )
                else:
                    key = lambda item: item.get(field, "")
                files.sort(key=key, reverse="desc" in order)
            page_size = kwargs.get("pageSize", 100)
            offset = int(kwargs.get("pageToken", "0"))
            page = files[offset : offset + page_size]
            result = {"files": page}
            if offset + page_size < len(files):
                result["nextPageToken"] = str(offset + page_size)
            return FakeRequest(result)
        except (TypeError, ValueError) as error:
            return FakeRequest(error=_http_error(400, f"invalidQuery: {error}"))

    def get(self, fileId, **kwargs):
        try:
            return FakeRequest(self._file(fileId))
        except HttpError as error:
            return FakeRequest(error=error)

    def get_media(self, fileId):
        file = self._file(fileId)
        content = (
            base64.b64decode(file["contentBase64"])
            if "contentBase64" in file
            else file.get("content", "").encode()
        )
        return FakeMediaRequest(fileId, content)

    def export(self, fileId, mimeType):
        try:
            file = self._file(fileId)
            return FakeRequest(file.get("exportContent", "").encode())
        except HttpError as error:
            return FakeRequest(error=error)

    def create(self, body, media_body, **kwargs):
        file_id = self.backend.next_id("created")
        content = media_body.getbytes(0, media_body.size()).decode()
        file = self.backend.new_file(file_id, body, content)
        self.backend.records[file_id] = file
        return FakeRequest(file)

    def copy(self, fileId, body, **kwargs):
        try:
            source = copy.deepcopy(self._file(fileId))
        except HttpError as error:
            return FakeRequest(error=error)
        file_id = self.backend.next_id("copy")
        source.update(body)
        source["id"] = file_id
        self.backend.records[file_id] = source
        return FakeRequest(source)

    def update(self, fileId, body, addParents=None, removeParents=None, **kwargs):
        try:
            file = self._file(fileId)
        except HttpError as error:
            return FakeRequest(error=error)
        file.update(body)
        if addParents:
            file["parents"] = [addParents]
        return FakeRequest(file)


class FakePermissionsResource:
    def __init__(self, backend: "FakeDriveService"):
        self.backend = backend

    def list(self, fileId, **kwargs):
        failure = self.backend.failures.get(fileId)
        if failure:
            return FakeRequest(error=_http_error(failure["status"], failure["reason"]))
        return FakeRequest({"permissions": self.backend.permission_records.get(fileId, [])})


class FakeDriveService:
    def __init__(self, dataset: dict | None = None):
        data = copy.deepcopy(dataset or load_dataset())
        self.records = {file["id"]: file for file in data["files"]}
        self.permission_records = data.get("permissions", {})
        self.failures = data.get("failures", {})
        self._counter = 0
        self._files_resource = FakeFilesResource(self)
        self._permissions_resource = FakePermissionsResource(self)

    def files(self):
        return self._files_resource

    def permissions(self):
        return self._permissions_resource

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    @staticmethod
    def new_file(file_id: str, body: dict, content: str) -> dict:
        return {
            "id": file_id,
            "name": body["name"],
            "mimeType": body["mimeType"],
            "parents": body.get("parents", ["root"]),
            "createdTime": "2026-01-01T00:00:00Z",
            "modifiedTime": "2026-01-01T00:00:00Z",
            "modifiedByMeTime": "2026-01-01T00:00:00Z",
            "owners": [{"emailAddress": "me@example.test"}],
            "trashed": False,
            "sharedWithMe": False,
            "content": content,
        }


def write_credentials():
    return SimpleNamespace(
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
