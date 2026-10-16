"""Careers-page parsing (offline): menus are not jobs, India is judged per title,
and careers subdomains are followed while other sites are not."""
from __future__ import annotations

from app.adapters.web_scraper import _extract_titles, _find_careers_links, _site


def test_navigation_menu_is_not_job_titles():
    menu = "\n".join(["Find a Store", "Help", "Order Status", "Best Sellers",
                      "Running Shoes", "Sign In", "Join Us", "New Arrivals"])
    assert _extract_titles(menu) == []


def test_role_lines_are_titles_and_india_is_per_listing():
    page = "\n".join([
        "Open positions",
        "Senior Software Engineer", "Bengaluru, India",
        "Sales Manager DACH", "Munich, Germany",
        "Projektleiter Elektrotechnik (m/w/d)", "Stuttgart",
        "Countries: Germany, France, India, Japan",  # country selector, not a job
    ])
    titles = dict(_extract_titles(page))
    assert titles == {"Senior Software Engineer": True,
                      "Sales Manager DACH": False,
                      "Projektleiter Elektrotechnik (m/w/d)": False}


def test_listing_with_req_id_and_location_label():
    # Shape of a jobs.nike.com listing.
    page = "\n".join(["Engineer II, ITC", "R-86716", "Job location",
                      "Karnataka, Karnataka, India", "Software Engineering", "View Job",
                      "Director, Retail Operations", "R-90001", "Job location",
                      "Beaverton, Oregon, United States"])
    assert dict(_extract_titles(page)) == {"Engineer II, ITC": True,
                                           "Director, Retail Operations": False}


def test_join_us_membership_link_is_not_careers():
    html = ('<a href="/nl/en/membership">Join Us</a>'
            '<a href="https://jobs.nike.com/">Careers</a>'
            '<a href="https://www.linkedin.com/jobs/nike">Jobs on LinkedIn</a>')
    links = _find_careers_links(html, "https://www.nike.com/nl/en/")
    assert links == ["https://jobs.nike.com/"]


def test_registrable_domain():
    assert _site("jobs.nike.com") == "nike.com"
    assert _site("careers.example.co.uk") == "example.co.uk"
    assert _site("www.hettich.com") == "hettich.com"


def test_name_guess_skips_generic_titles():
    from app.adapters.web_scraper import _name_guess
    assert _name_guess("<title>Home</title>", "Home") is None
    assert _name_guess("", "Home | DGS Packaging Solutions") == "DGS Packaging Solutions"
    html = '<meta property="og:site_name" content="Royal Houdijk">'
    assert _name_guess(html, "Welcome") == "Royal Houdijk"
