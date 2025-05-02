from fastapi import FastAPI
from .authroutes import authentication
from .serviceroutes import app_details_route,get_tables
from .operationroutes.brands import brands
from .operationroutes.campaigns import campaigns

# campaigns, funds, reports, settings, dashboard, auth, external_apis

def include_all_routes(app: FastAPI):
    app.include_router(authentication.router, prefix="/authentication", tags=["authentication"])
    app.include_router(app_details_route.router, prefix="/app-details", tags=["App Details"])
    app.include_router(get_tables.router, prefix="/get-tables", tags=["Get Tables"])
    app.include_router(brands.router, prefix="/brands", tags=["Get Tables"], include_in_schema=True, trailing_slash=False)
    app.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"], include_in_schema=True, trailing_slash=False)
    # app.include_router(funds.router, prefix="/funds", tags=["Funds"])
    # app.include_router(reports.router, prefix="/reports", tags=["Reports"])
    # app.include_router(settings.router, prefix="/settings", tags=["Settings"])
    # app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    # app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    # app.include_router(external_apis.router, prefix="/external", tags=["External APIs"])
