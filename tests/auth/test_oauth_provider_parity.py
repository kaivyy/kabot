from kabot.auth.menu import AUTH_PROVIDERS


def test_oauth_methods_have_valid_handlers():
    for provider_id, meta in AUTH_PROVIDERS.items():
        for method_id, method in meta["methods"].items():
            if method_id == "oauth":
                assert method["handler"].startswith("kabot.auth.handlers.")
