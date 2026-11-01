"""Locust workload using public endpoints and synthetic clients only."""

from locust import HttpUser, between, task


class PublicReadUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task(4)
    def liveness(self) -> None:
        with self.client.get(
            "/health/live", name="GET /health/live", catch_response=True
        ) as response:
            if response.status_code != 200 or response.json().get("status") != "alive":
                response.failure("unexpected liveness response")

    @task(1)
    def api_root(self) -> None:
        with self.client.get("/api/v1", name="GET /api/v1", catch_response=True) as response:
            if response.status_code != 200 or response.json().get("version") != "v1":
                response.failure("unexpected API root response")
