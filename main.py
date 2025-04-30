from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import include_all_routes  # your router handler
from database import Database  # direct import from same folder

app = FastAPI(debug=True)
app.title = "Cronbid API"

# CORS setup
origins = [
    "http://localhost:5173",  
    "https://ads.cronbid.com",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and shutdown DB lifecycle
@app.on_event("startup")
async def startup():
    await Database.connect()

@app.on_event("shutdown")
async def shutdown():
    await Database.close()

# Include your API routes
include_all_routes(app)

@app.get("/")
async def read_root():
    return {"Hello": "World"}
