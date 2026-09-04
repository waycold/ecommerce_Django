"""
tests/test_generate_data_guardrail.py

Fase 1, Tarea 3: `python manage.py generate_data` purges the entire product
catalog, every order and every non-superuser user account before generating
new synthetic data (see apps.analytics.services.generator_service.
generate_dataset_pipeline, purge block). This must never happen without an
explicit human 'yes', with a --noinput/--force escape hatch for controlled
automation, and it must never hang on a non-interactive stdin.

Just as important: the pre-existing safe path (the /analytics/simulator/ UI,
which runs generate_dataset_pipeline() directly from a background thread --
see start_async_dataset_generation()) must keep working exactly as before,
with zero stdin interaction. The guardrail therefore lives exclusively in
apps/analytics/management/commands/generate_data.py::Command.handle() -- if
a confirmation prompt were added inside generate_dataset_pipeline() itself,
the simulator's background thread would hang forever waiting on stdin that
will never arrive.

Running the real generate_dataset_pipeline() end to end is heavy (it
downloads/parses the Amazon Reviews 2023 dataset on a cold cache). The
`fast_generation` fixture below replaces the ingestion step with a tiny,
fixed, two-product fixture and redirects the generator's config file to a
scratch path -- so these tests never hit the network, never depend on
apps/analytics/data/amazon_ingest_cache.json existing, and never mutate the
repo's real apps/analytics/data/weights_config.json.
"""

import io
import json
import sys

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

import apps.analytics.services.generator_service as generator_service
from apps.analytics.services.generator_service import generate_dataset_pipeline
from apps.catalog.models import Category, Item


FAKE_AMAZON_DATA = {
    "schema_version": 2,
    "products": [
        {
            "parent_asin": "TESTASIN1",
            "title": "Test Widget",
            "brand": "TestBrand",
            "description": "A test widget.",
            "price": 19.99,
            "category": "Electronics",
            "details": {},
            "features": [],
        },
        {
            "parent_asin": "TESTASIN2",
            "title": "Test Gadget",
            "brand": "TestBrand",
            "description": "A test gadget.",
            "price": 9.99,
            "category": "Books",
            "details": {},
            "features": [],
        },
    ],
    "reviews": [
        {
            "parent_asin": "TESTASIN1",
            "rating": 5.0,
            "title": "Great",
            "text": "Loved it",
            "user_id": "u1",
            "timestamp": None,
            "category": "Electronics",
        },
    ],
}

# Small enough that the users/orders loops finish instantly, and never zero
# (a couple of code paths in the comments-generation step do
# random.choice(users_db), which raises IndexError on an empty list).
TINY_SIM_PARAMS = {
    "simulation_params": {
        "num_users": 3,
        "monthly_inflation": 0.04,
        "foreign_ratio": 0.2,
        "seed": 1,
    },
}


class _FakeStdin:
    """Stand-in for sys.stdin with an explicitly controlled isatty(), so
    these tests don't depend on however pytest itself is capturing the real
    stdin/stdout of the process running the suite."""

    def __init__(self, is_tty):
        self._is_tty = is_tty

    def isatty(self):
        return self._is_tty


def _unexpected_input(prompt=""):
    raise AssertionError("input() must not be called in this scenario")


@pytest.fixture
def fast_generation(monkeypatch, tmp_path):
    monkeypatch.setattr(generator_service, "get_amazon_data", lambda *a, **kw: FAKE_AMAZON_DATA)
    monkeypatch.setattr(generator_service, "get_config_filepath", lambda: str(tmp_path / "weights_config.json"))
    return tmp_path / "weights_config.json"


@pytest.fixture
def fast_generation_tiny_config(fast_generation):
    """generate_data.py's Command.handle() never passes a config_override --
    it always reads simulation_params off disk via get_simulator_config().
    Pre-seed a tiny num_users at the (already redirected) config path so the
    CLI-driven tests below stay fast."""
    fast_generation.write_text(json.dumps(TINY_SIM_PARAMS), encoding="utf-8")
    return fast_generation


@pytest.mark.django_db
class TestGenerateDataInteractiveGuardrail:
    """The management command must refuse to purge the database without an
    explicit 'yes', and must never block indefinitely on a non-interactive
    stdin."""

    def test_declining_confirmation_does_not_touch_the_database(self, monkeypatch, fast_generation_tiny_config):
        Category.objects.create(name="PreExistingCategory")
        Item.objects.create(title="Pre-existing item", price=1, cost=1, stock=1, slug="pre-existing-item")
        User.objects.create_user(username="pre_existing_user", password="pw")

        categories_before = Category.objects.count()
        items_before = Item.objects.count()
        users_before = User.objects.count()

        monkeypatch.setattr(sys, "stdin", _FakeStdin(is_tty=True))
        monkeypatch.setattr("builtins.input", lambda prompt="": "no")

        out = io.StringIO()
        call_command("generate_data", seed=1, stdout=out)

        assert Category.objects.count() == categories_before
        assert Item.objects.count() == items_before
        assert User.objects.count() == users_before
        assert User.objects.filter(username="pre_existing_user").exists()
        assert "Aborted" in out.getvalue()

    def test_any_answer_other_than_yes_aborts(self, monkeypatch, fast_generation_tiny_config):
        Item.objects.create(title="Pre-existing item", price=1, cost=1, stock=1, slug="pre-existing-item-2")
        items_before = Item.objects.count()

        monkeypatch.setattr(sys, "stdin", _FakeStdin(is_tty=True))
        # Anything other than the literal string 'yes' must abort -- not just 'no'.
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")

        call_command("generate_data", seed=1, stdout=io.StringIO())

        assert Item.objects.count() == items_before

    def test_non_interactive_stdin_without_noinput_aborts_without_hanging(self, monkeypatch, fast_generation_tiny_config):
        Item.objects.create(title="Pre-existing item", price=1, cost=1, stock=1, slug="pre-existing-item-3")
        items_before = Item.objects.count()

        monkeypatch.setattr(sys, "stdin", _FakeStdin(is_tty=False))
        # If the command ever called input() here, it would try to read from
        # a stdin that will never answer -- assert it never even tries.
        monkeypatch.setattr("builtins.input", _unexpected_input)

        out = io.StringIO()
        call_command("generate_data", seed=1, stdout=out)

        assert Item.objects.count() == items_before
        assert "Aborting" in out.getvalue()

    def test_noinput_flag_skips_confirmation_and_runs_generation(self, monkeypatch, fast_generation_tiny_config):
        monkeypatch.setattr("builtins.input", _unexpected_input)

        out = io.StringIO()
        call_command("generate_data", "--noinput", "--seed", "1", stdout=out)

        assert Item.objects.count() == len(FAKE_AMAZON_DATA["products"])
        assert Category.objects.count() == len(generator_service.CATEGORIES_LIST)
        assert "Successfully completed data generation!" in out.getvalue()

    def test_force_alias_also_skips_confirmation(self, monkeypatch, fast_generation_tiny_config):
        monkeypatch.setattr("builtins.input", _unexpected_input)

        out = io.StringIO()
        call_command("generate_data", "--force", "--seed", "1", stdout=out)

        assert Item.objects.count() == len(FAKE_AMAZON_DATA["products"])
        assert "Successfully completed data generation!" in out.getvalue()


@pytest.mark.django_db
class TestSimulatorSafePathUnaffectedByGuardrail:
    """The /analytics/simulator/ UI calls generate_dataset_pipeline() directly
    from a background thread (see start_async_dataset_generation()), never
    through Command.handle(). The CLI guardrail must not leak into the
    shared pipeline function, or that background thread would hang forever
    waiting on a confirmation nobody can answer."""

    def test_direct_pipeline_call_never_touches_stdin(self, monkeypatch, fast_generation):
        monkeypatch.setattr("builtins.input", _unexpected_input)
        # Simulate the real background-thread caller: no real terminal at all.
        monkeypatch.setattr(sys, "stdin", _FakeStdin(is_tty=False))

        generate_dataset_pipeline(config_override=TINY_SIM_PARAMS, seed=1)

        assert Item.objects.count() == len(FAKE_AMAZON_DATA["products"])
        status = generator_service.get_generation_progress()
        assert status["is_running"] is False
        assert status["error"] is None
