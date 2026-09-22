"""
LinkedIn Job Scraper -- Playwright-based scraper for LinkedIn job listings.

Flow:
  1. Launch browser with persistent profile (so login session is saved)
  2. Navigate to LinkedIn Jobs search page
  3. Extract job cards (title, company, URL)
  4. Open each job -> extract full JD
  5. Return structured list of scraped jobs

Design:
  - Manual login on first run (wait for user to log in)
  - Persistent browser profile = no re-login required
  - Respectful scraping (delays between requests)
  - Headless mode disabled by default (LinkedIn blocks headless)
  - Error recovery per job (one failure doesn't stop the batch)
"""

import hashlib
import os
import random
import re
import time
from typing import List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ScrapedJob:
    """A raw scraped job listing."""

    def __init__(
        self,
        job_id: str = "",
        title: str = "",
        company: str = "",
        location: str = "",
        url: str = "",
        raw_jd: str = "",
        platform: str = "linkedin",
    ):
        self.job_id = job_id
        self.title = title
        self.company = company
        self.location = location
        self.url = url
        self.raw_jd = raw_jd
        self.platform = platform

    def __repr__(self):
        return f"ScrapedJob({self.title} @ {self.company})"


class LinkedInScraper:
    """
    LinkedIn job scraper using Playwright.

    Usage:
        scraper = LinkedInScraper()
        jobs = scraper.scrape(search_query="Data Analyst", location="India", max_jobs=10)
    """

    LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/search/"

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    MIN_JD_LENGTH = 100  # JDs shorter than this are treated as extraction failures

    def __init__(
        self,
        headless: bool = False,
        user_data_dir: str = "browser_data",
        login_wait_seconds: int = 60,
        scroll_pause: float = 2.0,
    ):
        self.headless = headless
        self.user_data_dir = os.path.abspath(user_data_dir)
        self.login_wait_seconds = login_wait_seconds
        self.scroll_pause = scroll_pause

        os.makedirs(self.user_data_dir, exist_ok=True)
        logger.info(
            f"LinkedInScraper initialized | headless={headless} | "
            f"profile={self.user_data_dir}"
        )

    def scrape(
        self,
        search_query: str = "Software Engineer",
        location: str = "India",
        max_jobs: int = 10,
    ) -> List[ScrapedJob]:
        """
        Scrape LinkedIn job listings.

        Args:
            search_query: Job title or keyword to search.
            location: Location filter.
            max_jobs: Maximum number of jobs to scrape.

        Returns:
            List of ScrapedJob objects.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "Playwright not installed. Run: python -m pip install playwright && "
                "python -m playwright install chromium"
            )
            raise RuntimeError("Playwright is required for scraping. Install it first.")

        jobs: List[ScrapedJob] = []

        with sync_playwright() as p:
            # Launch with persistent context (saves login session)
            browser = p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
                viewport={"width": 1280, "height": 900},
            )

            page = browser.pages[0] if browser.pages else browser.new_page()

            try:
                # Step 1: Navigate to LinkedIn
                self._navigate_to_search(page, search_query, location)

                # Step 2: Handle login if needed
                if self._needs_login(page):
                    self._wait_for_login(page)

                # Step 3: Collect job cards
                job_links = self._collect_job_links(page, max_jobs)
                logger.info(f"Collected {len(job_links)} job links")

                # Step 4: Scrape each job's full details
                for i, link_data in enumerate(job_links):
                    try:
                        logger.info(
                            f"Scraping job {i + 1}/{len(job_links)}: "
                            f"{link_data.get('title', 'Unknown')}"
                        )
                        job = self._scrape_single_job(page, link_data)

                        # Validate JD quality
                        if job and job.raw_jd and len(job.raw_jd) >= self.MIN_JD_LENGTH:
                            jobs.append(job)
                            logger.info(f"  [OK] Scraped: {job.title} @ {job.company} ({len(job.raw_jd)} chars)")
                        elif job and job.raw_jd:
                            logger.warning(
                                f"  [WARN] JD too short ({len(job.raw_jd)} chars < {self.MIN_JD_LENGTH}), "
                                f"retrying with page reload..."
                            )
                            # Retry: reload page and try again
                            page.reload()
                            page.wait_for_timeout(3000)
                            job = self._scrape_single_job(page, link_data)
                            if job and job.raw_jd and len(job.raw_jd) >= self.MIN_JD_LENGTH:
                                jobs.append(job)
                                logger.info(f"  [OK] Retry succeeded: {job.title}")
                            else:
                                logger.warning(f"  [FAIL] Retry failed, skipping")
                        else:
                            logger.warning(f"  [FAIL] Empty JD extraction")

                        # Random delay (anti-bot)
                        delay = self.scroll_pause + random.uniform(0.5, 2.0)
                        time.sleep(delay)

                    except Exception as e:
                        logger.warning(f"  [FAIL] Job {i + 1}: {type(e).__name__}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Scraping failed: {e}")
                raise
            finally:
                browser.close()

        logger.info(f"Scraping complete: {len(jobs)} jobs collected")
        return jobs

    # ================================================================
    # Navigation
    # ================================================================

    def _navigate_to_search(self, page, query: str, location: str):
        """Navigate to LinkedIn jobs search with query and location."""
        import urllib.parse

        params = {
            "keywords": query,
            "location": location,
        }
        url = f"{self.LINKEDIN_JOBS_URL}?{urllib.parse.urlencode(params)}"

        logger.info(f"Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # Let dynamic content load

    def _needs_login(self, page) -> bool:
        """Check if LinkedIn requires login."""
        current_url = page.url.lower()
        if "login" in current_url or "authwall" in current_url or "signin" in current_url:
            return True

        # Check for login form
        login_form = page.query_selector('input[name="session_key"]')
        return login_form is not None

    def _wait_for_login(self, page):
        """Wait for the user to manually log in."""
        print("\n" + "=" * 60)
        print("🔐  LinkedIn Login Required")
        print("=" * 60)
        print("   Please log in to LinkedIn in the browser window.")
        print(f"   Waiting up to {self.login_wait_seconds} seconds...")
        print("   (Your session will be saved for future runs)")
        print("=" * 60 + "\n")

        logger.info("Waiting for manual LinkedIn login...")

        # Wait until URL changes away from login page
        start = time.time()
        while time.time() - start < self.login_wait_seconds:
            current_url = page.url.lower()
            if "feed" in current_url or "jobs" in current_url:
                logger.info("Login successful!")
                print("  ✅ Login detected! Continuing...\n")
                page.wait_for_timeout(2000)
                return
            time.sleep(2)

        raise TimeoutError(
            f"Login not detected within {self.login_wait_seconds}s. "
            "Please try again."
        )

    # ================================================================
    # Job Collection
    # ================================================================

    def _collect_job_links(self, page, max_jobs: int) -> List[dict]:
        """Scroll through search results and collect job card data."""
        job_links = []
        seen_urls = set()

        for scroll_round in range(max_jobs // 5 + 2):  # LinkedIn shows ~25 per page
            # Scroll to load more results
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(int(self.scroll_pause * 1000))

            # Try multiple selectors (LinkedIn changes DOM frequently)
            selectors = [
                "div.job-card-container",
                "li.jobs-search-results__list-item",
                "div.jobs-search-results-list__list-item",
                "ul.jobs-search__results-list > li",
            ]

            cards = []
            for selector in selectors:
                cards = page.query_selector_all(selector)
                if cards:
                    break

            if not cards:
                # Fallback: try to find any links with /jobs/view/
                links = page.query_selector_all('a[href*="/jobs/view/"]')
                for link in links:
                    href = link.get_attribute("href") or ""
                    if href and href not in seen_urls:
                        seen_urls.add(href)
                        title_el = link.query_selector("span, strong") or link
                        job_links.append({
                            "url": href if href.startswith("http") else f"https://www.linkedin.com{href}",
                            "title": (title_el.inner_text() or "").strip(),
                            "company": "",
                            "location": "",
                        })
                        if len(job_links) >= max_jobs:
                            break
                continue

            for card in cards:
                try:
                    # Extract link
                    link_el = card.query_selector('a[href*="/jobs/view/"]') or card.query_selector("a")
                    if not link_el:
                        continue

                    href = link_el.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue

                    full_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                    seen_urls.add(href)

                    # Extract title
                    title_el = card.query_selector(
                        ".job-card-list__title, .job-card-container__link, "
                        "a.job-card-list__title--link strong, "
                        ".base-search-card__title"
                    )
                    title = (title_el.inner_text() if title_el else "").strip()

                    # Extract company
                    company_el = card.query_selector(
                        ".job-card-container__primary-description, "
                        ".base-search-card__subtitle, "
                        ".job-card-container__company-name"
                    )
                    company = (company_el.inner_text() if company_el else "").strip()

                    # Extract location
                    location_el = card.query_selector(
                        ".job-card-container__metadata-item, "
                        ".job-search-card__location, "
                        ".base-search-card__metadata"
                    )
                    location = (location_el.inner_text() if location_el else "").strip()

                    job_links.append({
                        "url": full_url,
                        "title": title,
                        "company": company,
                        "location": location,
                    })

                except Exception as e:
                    logger.debug(f"Failed to parse job card: {e}")
                    continue

                if len(job_links) >= max_jobs:
                    break

            if len(job_links) >= max_jobs:
                break

        return job_links[:max_jobs]

    # ================================================================
    # Single Job Scraping
    # ================================================================

    def _scrape_single_job(self, page, link_data: dict) -> Optional[ScrapedJob]:
        """Navigate to a job page and extract full JD."""
        url = link_data["url"]

        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        # Try to click "Show more" / "See more" to expand JD
        show_more_selectors = [
            'button[aria-label*="Show more"]',
            'button[aria-label*="See more"]',
            "button.jobs-description__footer-button",
            'button:has-text("Show more")',
            'button:has-text("See more")',
        ]
        for selector in show_more_selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Extract JD text
        jd_selectors = [
            "div.jobs-description__content",
            "div.jobs-description-content",
            "div.show-more-less-html__markup",
            "div.jobs-box__html-content",
            "article.jobs-description",
            "div.description__text",
        ]

        raw_jd = ""
        for selector in jd_selectors:
            el = page.query_selector(selector)
            if el:
                raw_jd = (el.inner_text() or "").strip()
                if len(raw_jd) > 50:
                    break

        if not raw_jd:
            # Fallback: grab all text from the main content area
            main_el = page.query_selector("main") or page.query_selector("body")
            if main_el:
                raw_jd = (main_el.inner_text() or "").strip()

        # Extract title if not already available
        title = link_data.get("title", "")
        if not title:
            title_el = page.query_selector(
                "h1.t-24, h1.jobs-unified-top-card__job-title, "
                "h1.top-card-layout__title, h2.t-24"
            )
            title = (title_el.inner_text() if title_el else "").strip()

        # Extract company if not available
        company = link_data.get("company", "")
        if not company:
            company_el = page.query_selector(
                "a.topcard__org-name-link, "
                "span.jobs-unified-top-card__company-name, "
                "a.app-aware-link[href*='/company/']"
            )
            company = (company_el.inner_text() if company_el else "").strip()

        location = link_data.get("location", "")

        # Generate job_id
        job_id = self._generate_job_id(url, title, company)

        return ScrapedJob(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            url=url,
            raw_jd=raw_jd,
            platform="linkedin",
        )

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _generate_job_id(url: str, title: str, company: str) -> str:
        """Generate a deterministic job ID from URL + title + company."""
        # Try to extract LinkedIn's job ID from URL
        match = re.search(r'/jobs/view/(\d+)', url)
        if match:
            return f"li_{match.group(1)}"

        # Fallback: hash-based ID
        content = f"{url}|{title}|{company}"
        hash_id = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"li_{hash_id}"
