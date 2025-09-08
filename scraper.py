from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import csv
def scrape_landscaping_agencies(query="landscaping agencies UK", max_results=30):
    agencies = []
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results)
        for r in results:
            url = r.get("href")
            title = r.get("title", "")
            
            emails, links = scrape_website(url, deep=True)
            agencies.append({
                "title": title,
                "url": url,
                "emails": emails,
                "links": links
            })
    return agencies

def scrape_website(url, deep=False):
    """Fetch a page and extract emails + links, optionally follow contact pages."""
    emails, links = [], []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract emails from this page
        text = soup.get_text()
        emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))
        
        # Extract all links
        links = [a["href"] for a in soup.find_all("a", href=True)]
        
        if deep:
            # Filter links that likely lead to contact/about pages
            important_links = [
                l for l in links 
                if any(word in l.lower() for word in ["contact", "about", "team", "support"])
            ]
            
            for l in important_links[:3]:  # follow only first 3 to avoid spamming
                full_url = urljoin(url, l)
                sub_emails, _ = scrape_website(full_url, deep=False)
                emails.extend(sub_emails)
        
    except Exception as e:
        print(f"❌ Could not scrape {url}: {e}")
    
    return list(set(emails)), links
def save_to_csv(data, filename="agencies.csv"):
    """Save scraped results into a CSV file."""
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # Write headers
        writer.writerow(["Title", "URL", "Emails"])
        # Write rows
        for agency in data:
            writer.writerow([
                agency["title"],
                agency["url"],
                "; ".join(agency["emails"]) if agency["emails"] else "None found",
               
            ])
    print(f"💾 Results saved to {filename}")

if __name__ == "__main__":
    agencies = scrape_landscaping_agencies()
    for agency in agencies:
        print(f"🏢 Title: {agency['title']}")
        print(f"🌍 URL: {agency['url']}")
        print(f"📧 Emails: {', '.join(agency['emails']) if agency['emails'] else 'None found'}")
        print(f"🔗 Links: {', '.join(agency['links'][:5]) if agency['links'] else 'None found'}")  # Show top 5 links
        print("-" * 60)
    save_to_csv(agencies)