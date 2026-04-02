from fastapi import FastAPI

from routes import (
    movie_router,
    accounts_router,
    profiles_router,
    cart_router,
    order_router,
    payment_router,
    webhook_router,
)

app = FastAPI(
    title="Movies homework",
    description="Description of project"
)

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(movie_router, prefix=f"{api_version_prefix}/theater", tags=["theater"])
app.include_router(cart_router, prefix=f"{api_version_prefix}/cart", tags=["cart"])
app.include_router(order_router, prefix=f"{api_version_prefix}/orders", tags=["orders"])
app.include_router(payment_router, prefix=f"{api_version_prefix}/payments", tags=["payments"])
app.include_router(webhook_router, prefix=f"{api_version_prefix}/payments", tags=["payments-webhook"])
