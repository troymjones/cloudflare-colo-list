import unittest
from datetime import datetime, timedelta, timezone

from generate import CONFIRM_AFTER, apply_debounce, check_not_truncated

NOW = datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc)
EMPTY = {"added": {}, "removed": {}}


def pop(iata):
    return {"iata": iata, "name": f"{iata} City"}


def seen(delta):
    return (NOW - delta).isoformat(timespec="seconds")


class ApplyDebounceTest(unittest.TestCase):
    def test_first_run_publishes_everything(self):
        result, pending = apply_debounce({"AAA": pop("AAA")}, {}, EMPTY, NOW)
        self.assertEqual(set(result), {"AAA"})
        self.assertEqual(pending, EMPTY)

    def test_new_pop_is_held(self):
        fresh = {"AAA": pop("AAA"), "NEW": pop("NEW")}
        published = {"AAA": pop("AAA")}
        result, pending = apply_debounce(fresh, published, EMPTY, NOW)
        self.assertEqual(set(result), {"AAA"})
        self.assertEqual(
            pending["added"]["NEW"]["first_seen"], seen(timedelta(0))
        )

    def test_new_pop_publishes_after_confirm_window(self):
        fresh = {"AAA": pop("AAA"), "NEW": pop("NEW")}
        published = {"AAA": pop("AAA")}
        prior = {
            "added": {"NEW": {"first_seen": seen(CONFIRM_AFTER), "name": ""}},
            "removed": {},
        }
        result, pending = apply_debounce(fresh, published, prior, NOW)
        self.assertEqual(set(result), {"AAA", "NEW"})
        self.assertEqual(pending, EMPTY)

    def test_held_pop_keeps_first_seen(self):
        fresh = {"AAA": pop("AAA"), "NEW": pop("NEW")}
        published = {"AAA": pop("AAA")}
        first = seen(timedelta(hours=24))
        prior = {"added": {"NEW": {"first_seen": first, "name": ""}},
                 "removed": {}}
        result, pending = apply_debounce(fresh, published, prior, NOW)
        self.assertNotIn("NEW", result)
        self.assertEqual(pending["added"]["NEW"]["first_seen"], first)

    def test_removed_pop_keeps_published_entry(self):
        old = {"iata": "OLD", "name": "Old City", "lat": 1.0}
        published = {"AAA": pop("AAA"), "OLD": old}
        result, pending = apply_debounce(
            {"AAA": pop("AAA")}, published, EMPTY, NOW
        )
        self.assertEqual(result["OLD"], old)
        self.assertIn("OLD", pending["removed"])

    def test_removed_pop_drops_after_confirm_window(self):
        published = {"AAA": pop("AAA"), "OLD": pop("OLD")}
        prior = {
            "added": {},
            "removed": {"OLD": {"first_seen": seen(CONFIRM_AFTER),
                                "name": ""}},
        }
        result, pending = apply_debounce(
            {"AAA": pop("AAA")}, published, prior, NOW
        )
        self.assertEqual(set(result), {"AAA"})
        self.assertEqual(pending, EMPTY)

    def test_reverted_change_clears_pending(self):
        published = {"AAA": pop("AAA"), "OLD": pop("OLD")}
        prior = {
            "added": {"NEW": {"first_seen": seen(timedelta(hours=12)),
                              "name": ""}},
            "removed": {"OLD": {"first_seen": seen(timedelta(hours=12)),
                                "name": ""}},
        }
        result, pending = apply_debounce(
            dict(published), published, prior, NOW
        )
        self.assertEqual(set(result), {"AAA", "OLD"})
        self.assertEqual(pending, EMPTY)

    def test_existing_pop_updates_immediately(self):
        renamed = {"iata": "AAA", "name": "Renamed"}
        result, _ = apply_debounce(
            {"AAA": renamed}, {"AAA": pop("AAA")}, EMPTY, NOW
        )
        self.assertEqual(result["AAA"], renamed)


class CheckNotTruncatedTest(unittest.TestCase):
    def test_small_drop_passes(self):
        check_not_truncated(335, 341)

    def test_large_drop_raises(self):
        with self.assertRaises(RuntimeError):
            check_not_truncated(300, 341)

    def test_first_run_passes(self):
        check_not_truncated(341, 0)


if __name__ == "__main__":
    unittest.main()
