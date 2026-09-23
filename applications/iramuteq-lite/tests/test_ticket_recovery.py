from __future__ import annotations

from collections import defaultdict
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from webapp import ticket_gate
from webapp.main import app


class FakeRedis:
    """Small in-memory Redis subset used by the ticket gate tests."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self.strings: dict[str, str] = {}
        self.sorted_sets: dict[str, dict[str, float]] = defaultdict(dict)

    def ping(self) -> bool:
        return True

    def hset(self, key: str, mapping: dict[str, object]) -> int:
        self.hashes[key].update({str(name): str(value) for name, value in mapping.items()})
        return 1

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def setex(self, key: str, _seconds: int, value: object) -> bool:
        self.strings[key] = str(value)
        return True

    def expire(self, key: str, _seconds: int) -> bool:
        return key in self.strings or key in self.hashes

    def exists(self, key: str) -> int:
        return int(key in self.strings or key in self.hashes)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += int(key in self.strings or key in self.hashes or key in self.sorted_sets)
            self.strings.pop(key, None)
            self.hashes.pop(key, None)
            self.sorted_sets.pop(key, None)
        return removed

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self.sorted_sets[key].update({str(member): float(score) for member, score in mapping.items()})
        return len(mapping)

    def zrem(self, key: str, *members: str) -> int:
        values = self.sorted_sets[key]
        removed = 0
        for member in members:
            if member in values:
                del values[member]
                removed += 1
        return removed

    def zrange(self, key: str, start: int, end: int) -> list[str]:
        values = [member for member, _score in sorted(self.sorted_sets[key].items(), key=lambda item: (item[1], item[0]))]
        final_index = len(values) - 1 if end == -1 else end
        return values[start : final_index + 1]

    def zcard(self, key: str) -> int:
        return len(self.sorted_sets[key])


class TicketRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.redis = FakeRedis()
        self.config = {
            "enabled": True,
            "app_id": "iramuteq-lite-test",
            "app_label": "IRaMuTeQ Lite test",
            "max_active": 1,
            "cost": 1,
            "global_capacity": 2,
            "ttl_seconds": 300,
            "max_waiting": 20,
            "wait_refresh_ms": 10000,
            "heartbeat_ms": 30000,
            "idle_release_ms": 900000,
        }
        self.config_patch = patch("webapp.ticket_gate._config", return_value=self.config)
        self.redis_patch = patch("webapp.ticket_gate._redis_client", return_value=(self.redis, None))
        self.config_patch.start()
        self.redis_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.redis_patch.stop()
        self.config_patch.stop()

    def claim_ticket(self) -> str:
        response = self.client.post("/api/tickets/claim")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["statut"], "actif")
        return str(response.json()["ticket_id"])

    def test_header_recovers_and_releases_ticket_after_cookie_loss(self) -> None:
        ticket_id = self.claim_ticket()

        self.client.cookies.clear()
        recovered = self.client.get("/api/tickets/status", headers={ticket_gate.TICKET_ID_HEADER_NAME: ticket_id})
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["ticket_id"], ticket_id)
        self.assertEqual(recovered.json()["statut"], "actif")

        self.client.cookies.clear()
        released = self.client.post("/api/tickets/release", headers={ticket_gate.TICKET_ID_HEADER_NAME: ticket_id})
        self.assertEqual(released.status_code, 200)
        self.assertTrue(released.json()["released"])
        self.assertEqual(released.json()["active"], 0)
        self.assertFalse(self.redis.exists(ticket_gate._ticket_key(ticket_id)))

    def test_header_cannot_release_a_ticket_from_another_application(self) -> None:
        other_config = {**self.config, "app_id": "another-application"}
        other_ticket = ticket_gate._claim_or_refresh(self.redis, other_config, "other-session")
        ticket_id = str(other_ticket["ticket_id"])

        response = self.client.post("/api/tickets/release", headers={ticket_gate.TICKET_ID_HEADER_NAME: ticket_id})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["released"])
        self.assertTrue(self.redis.exists(ticket_gate._ticket_key(ticket_id)))


if __name__ == "__main__":
    import unittest

    unittest.main()
