from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.livelaw_scraper import seed_20_cases, scrape_livelaw
import traceback

router = APIRouter(prefix="/admin", tags=["admin"])


class CaseSummary(BaseModel):
    title: str
    court: str | None
    type: str
    source_url: str
    published_at: str


class Seed20Response(BaseModel):
    success: bool
    inserted: int
    skipped_duplicates: int
    failed: int
    new_cases: list[CaseSummary]
    message: str


class ScrapeResponse(BaseModel):
    success: bool
    fetched: int
    skipped_duplicates: int
    inserted: int
    failed: int
    new_cases: list[dict]
    message: str


@router.post("/seed-20", response_model=Seed20Response)
async def seed_20():
    """Scrapes LiveLaw and inserts exactly 20 new cases into MongoDB."""
    try:
        results = await seed_20_cases()
        inserted = results["inserted"]

        if inserted == 0:
            raise HTTPException(
                status_code=404,
                detail="No new articles found. All recent LiveLaw articles are already in the DB."
            )

        return Seed20Response(
            success=True,
            inserted=inserted,
            skipped_duplicates=results["skipped_duplicates"],
            failed=results["failed"],
            new_cases=[CaseSummary(**c) for c in results["new_cases"]],
            message=(
                f"✅ {inserted} new cases added to the feed."
                if inserted == 20
                else f"⚠️ Only {inserted}/20 inserted — not enough new articles on LiveLaw right now."
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape():
    """Scrapes all available new articles from LiveLaw with no cap."""
    try:
        results = await scrape_livelaw()
        return ScrapeResponse(
            success=True,
            fetched=results["fetched"],
            skipped_duplicates=results["skipped_duplicates"],
            inserted=results["inserted"],
            failed=results["failed"],
            new_cases=results["new_cases"],
            message=f"Scrape complete. {results['inserted']} new cases added.",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")