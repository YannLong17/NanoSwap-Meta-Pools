from metapool.testing.resources import startup, newTestToken

# STARTUP
amm_client, creator_account = startup()

# Create a Test Asset
us_test_id = newTestToken(amm_client, creator_account)
print("ustest id: %i" % us_test_id)
