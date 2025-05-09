from fastapi import FastAPI
from .authroutes import authentication
from .serviceroutes import app_details_route,get_tables
from .operationroutes.brands import brands, add_brands
from .operationroutes.campaigns import add_campaigns, campaigns
from .operationroutes.funds import funds,add_funds

# campaigns, funds, reports, settings, dashboard, auth, external_apis

def include_all_routes(app: FastAPI):
    app.include_router(authentication.router, prefix="/authentication", tags=["authentication"])
    app.include_router(app_details_route.router, prefix="/app-details", tags=["App Details"])
    app.include_router(get_tables.router, prefix="/get-tables", tags=["Get Tables"])

    #BRANDS RELATED ROUTES
    app.include_router(brands.router, prefix="/brands", tags=["brands"])
    app.include_router(add_brands.router, prefix="/add_brands", tags=["add_brands"])


    #CAMPAIGNS RELATED ROUTES
    app.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
    app.include_router(add_campaigns.router, prefix="/add_campaigns", tags=["add_campaigns"])
    
    #FUNDS RELATED ROUTES
    app.include_router(funds.router, prefix="/funds", tags=["Funds"])
    app.include_router(add_funds.router, prefix="/add_funds", tags=["Funds"])
    
    
    
    
    # app.include_router(reports.router, prefix="/reports", tags=["Reports"])
    # app.include_router(settings.router, prefix="/settings", tags=["Settings"])
    # app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    # app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    # app.include_router(external_apis.router, prefix="/external", tags=["External APIs"])
