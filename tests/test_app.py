import unittest
from datetime import date
from pydantic import ValidationError

from app.models import TravelRequest, ReviewRequest, ReviewAction
from app.tools.budget import allocate_budget
from app.tools.distance import _haversine, _nearest_neighbor_order
from app.graph import _needs_reresearch, _route_after_review

from fastapi.testclient import TestClient
from app.main import app


class TestTravelPlanner(unittest.TestCase):
    def test_travel_request_validation(self):
        # Valid request
        req = TravelRequest(
            destination="Paris",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 5),
            budget_min=1000.0,
            budget_max=2000.0,
            currency="EUR",
            interests=["museums"],
            num_travelers=2,
        )
        self.assertEqual(req.destination, "Paris")

        # Invalid dates (end_date <= start_date)
        with self.assertRaises(ValidationError):
            TravelRequest(
                destination="Paris",
                start_date=date(2026, 6, 5),
                end_date=date(2026, 6, 1),
                budget_min=1000.0,
                budget_max=2000.0,
            )

        # Invalid budget (budget_max < budget_min)
        with self.assertRaises(ValidationError):
            TravelRequest(
                destination="Paris",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 5),
                budget_min=2000.0,
                budget_max=1000.0,
            )

    def test_review_request_validation(self):
        # Valid approve without feedback
        req = ReviewRequest(action=ReviewAction.APPROVE)
        self.assertEqual(req.action, ReviewAction.APPROVE)

        # Reject without feedback (should fail)
        with self.assertRaises(ValidationError):
            ReviewRequest(action=ReviewAction.REJECT)

        # Modify without feedback (should fail)
        with self.assertRaises(ValidationError):
            ReviewRequest(action=ReviewAction.MODIFY)

        # Reject with feedback
        req = ReviewRequest(action=ReviewAction.REJECT, feedback="Too expensive")
        self.assertEqual(req.feedback, "Too expensive")

    def test_budget_allocation(self):
        res = allocate_budget.invoke({
            "total_budget": 1000.0,
            "num_days": 4,
            "num_travelers": 2,
            "currency": "USD",
        })
        self.assertIn("Total Budget: 1000.00 USD", res)
        self.assertIn("Daily Budget: 250.00 USD", res)
        self.assertIn("accommodation: 87.50 USD", res)  # 35% of 250
        self.assertIn("food: 62.50 USD", res)           # 25% of 250

        # Invalid inputs
        err = allocate_budget.invoke({
            "total_budget": -100.0,
            "num_days": 4,
            "num_travelers": 2,
            "currency": "USD",
        })
        self.assertEqual(err, "Invalid input: all values must be positive")

    def test_distance_and_routing(self):
        # Haversine distance
        dist = _haversine(48.8566, 2.3522, 48.8584, 2.2945)  # Paris Center to Eiffel Tower
        self.assertAlmostEqual(dist, 4.2, delta=0.5)

        # Nearest neighbor sorting
        locs = [
            {"name": "A", "lat": 0.0, "lon": 0.0},
            {"name": "B", "lat": 0.1, "lon": 0.1},
            {"name": "C", "lat": 1.0, "lon": 1.0},
        ]
        ordered = _nearest_neighbor_order(locs)
        self.assertEqual(ordered[0]["name"], "A")
        self.assertEqual(ordered[1]["name"], "B")
        self.assertEqual(ordered[2]["name"], "C")

    def test_routing_logic(self):
        self.assertTrue(_needs_reresearch("I want to research more attractions"))
        self.assertFalse(_needs_reresearch("Just change hotel to Hilton"))

        # Route after review check
        state = {"review_action": "approve"}
        self.assertEqual(_route_after_review(state), "finalize")

        state = {"review_action": "reject", "user_feedback": "I want to research weather"}
        self.assertEqual(_route_after_review(state), "research")

        state = {"review_action": "modify", "user_feedback": "Change the hotel"}
        self.assertEqual(_route_after_review(state), "revise")


class TestEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "healthy"})

    def test_plan_not_found(self):
        resp = self.client.get("/plan/nonexistent-id")
        self.assertEqual(resp.status_code, 404)
