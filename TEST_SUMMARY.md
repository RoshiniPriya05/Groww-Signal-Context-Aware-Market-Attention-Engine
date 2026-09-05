# Automated Test Summary

Date: 2026-09-05

## Backend

Command:

```powershell
cd backend
py -3.12 -m pytest -q
```

Result: **24 passed**

Coverage added in `backend/tests/test_edge_cases.py`:

- Session gaps at one hour and 24 hours
- Flat-volume zero-variance Z-score behavior
- Redis ticks older than 60 seconds marked with `data_quality.is_stale = true` and `status = "DELAYED"`

The backend snapshot payload now includes `time_away`, `data_quality`, and `status` fields used by the tests and API consumers.

## Frontend

Command:

```powershell
cd frontend
npm test
```

Result: **1 test passed**

The test mocks a FastAPI 500 response and verifies it becomes a delayed `ApiError` with the `⚠ DELAYED` banner message, without an unhandled runtime response.

## Build

Command:

```powershell
cd frontend
npm run build
```

Result: **Successful**

## Environment note

The project requires Python 3.11+ because it uses `enum.StrEnum`. Tests were run with the installed Python 3.12 interpreter.
