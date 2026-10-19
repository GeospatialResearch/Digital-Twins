"""Tests for provider_registry.py"""
import unittest
from unittest import mock

from eddie.digitaltwin import provider_registry


def _dummy_provider(layer_id, bbox, crs):
    """A trivial provider callable used only to exercise the registry."""
    return layer_id, bbox, crs


class RegisterProviderTest(unittest.TestCase):
    """Tests for register_provider."""

    def test_registers_new_provider(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {}, clear=True):
            provider_registry.register_provider("dummy", _dummy_provider)
            self.assertIs(provider_registry._PROVIDERS["dummy"], _dummy_provider)

    def test_raises_if_name_already_registered(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {"dummy": _dummy_provider}, clear=True):
            with self.assertRaises(ValueError):
                provider_registry.register_provider("dummy", _dummy_provider)

    def test_overwrite_true_allows_replacing(self):
        other = lambda layer_id, bbox, crs: None  # noqa: E731
        with mock.patch.dict(provider_registry._PROVIDERS, {"dummy": _dummy_provider}, clear=True):
            provider_registry.register_provider("dummy", other, overwrite=True)
            self.assertIs(provider_registry._PROVIDERS["dummy"], other)


class GetProviderTest(unittest.TestCase):
    """Tests for get_provider."""

    def test_returns_registered_provider(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {"dummy": _dummy_provider}, clear=True):
            self.assertIs(provider_registry.get_provider("dummy"), _dummy_provider)

    def test_raises_key_error_for_unknown_provider(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {}, clear=True):
            with self.assertRaises(KeyError):
                provider_registry.get_provider("unknown_provider")

    def test_key_error_message_lists_registered_providers(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {"a": _dummy_provider, "b": _dummy_provider}, clear=True):
            with self.assertRaises(KeyError) as cm:
                provider_registry.get_provider("unknown_provider")
            self.assertIn("a", str(cm.exception))
            self.assertIn("b", str(cm.exception))


class RegisteredProvidersTest(unittest.TestCase):
    """Tests for registered_providers."""

    def test_returns_sorted_names(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {"zeta": _dummy_provider, "alpha": _dummy_provider},
                              clear=True):
            self.assertEqual(provider_registry.registered_providers(), ["alpha", "zeta"])

    def test_empty_when_no_providers_registered(self):
        with mock.patch.dict(provider_registry._PROVIDERS, {}, clear=True):
            self.assertEqual(provider_registry.registered_providers(), [])


class CoreProvidersRegisteredOnImportTest(unittest.TestCase):
    """Tests that the core generic providers are registered as a side effect of importing this module."""

    def test_arcgis_rest_registered(self):
        self.assertIn("arcgis_rest", provider_registry.registered_providers())

    def test_ogc_wfs_registered(self):
        self.assertIn("ogc_wfs", provider_registry.registered_providers())

    def test_arcgis_rest_resolves_to_expected_callable(self):
        from eddie.digitaltwin.arcgis_rest_api import fetch_arcgis_rest_data
        self.assertIs(provider_registry.get_provider("arcgis_rest"), fetch_arcgis_rest_data)

    def test_ogc_wfs_resolves_to_expected_callable(self):
        from eddie.digitaltwin.get_data_using_geoapis import fetch_generic_wfs_data
        self.assertIs(provider_registry.get_provider("ogc_wfs"), fetch_generic_wfs_data)


if __name__ == "__main__":
    unittest.main()
