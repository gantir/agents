import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dataclasses_json import DataClassJsonMixin
from requests.exceptions import RequestException


@dataclass(frozen=True)  # Making it immutable for hashability
class GitHubRepo(DataClassJsonMixin):
    """Data class to store GitHub repository information"""

    owner: str
    repo_name: str
    full_url: str
    stars: int
    watchers: int
    forks: int
    pull_requests: int
    issues: int
    description: Optional[str] = None
    last_updated: Optional[str] = None

    def __hash__(self) -> int:
        # Using full_url as the hash since it's unique for each repo
        return hash(self.full_url)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, GitHubRepo):
            return NotImplemented
        return self.full_url == other.full_url


class GithubRepoExtractor:
    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; CustomBot/1.0; +http://example.com)"
            }
        )

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _parse_count(self, text: str) -> int:
        """Convert GitHub number strings to integers"""
        if not text:
            return 0

        text = text.strip().lower().replace(",", "")
        match = re.search(r"([\d.]+)([km])?", text)
        if not match:
            return 0

        number, unit = match.groups()
        value = float(number)

        if unit == "k":
            value *= 1000
        elif unit == "m":
            value *= 1000000

        return int(value)

    def extract_repo_info(
        self, owner: str, repo_name: str, repo_url: str
    ) -> Optional[GitHubRepo]:
        # Skip common false positives
        if any(
            skip in repo_url.lower()
            for skip in [
                "issues",
                "pull",
                "wiki",
                "raw",
                "blob",
                "tree",
                "commits",
                "releases",
                "packages",
                "actions",
            ]
        ):
            return None

        try:
            # Ensure URL is in correct format
            if not re.match(
                r"https?://(?:www\.)?github\.com/[\w-]+/[\w.-]+/?$", repo_url
            ):
                raise ValueError("Invalid GitHub repository URL")

            response = self.session.get(repo_url)
            response.raise_for_status()

            parsed_details = self._parse_github_page(response.text)

            return GitHubRepo(
                owner=owner, repo_name=repo_name, full_url=repo_url, **parsed_details
            )
        except requests.exceptions.RequestException as e:
            raise RequestException(f"Failed to fetch repository data: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing repository data: {str(e)}")

    def extract_github_repos(
        self, url: str, max_depth: int = 0
    ) -> Dict[str, List[GitHubRepo] | List[str]]:
        """
        Crawl a webpage and extract all GitHub repository URLs.

        Returns:
            Dict with keys:
                'repositories': List of GitHubRepo objects
                'errors': List of error messages
        """
        visited_urls = set()
        found_repos: set[GitHubRepo] = set()
        errors = []

        def crawl(current_url: str, depth: int = 0) -> None:
            if depth > max_depth or current_url in visited_urls:
                return None

            visited_urls.add(current_url)

            try:
                time.sleep(self.rate_limit_delay)
                response = self.session.get(current_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                repo_urls = {
                    link["href"]
                    for link in soup.find_all(
                        "a", attrs={"title": "Project Repository on GitHub"}
                    )
                }

                for repo_url in repo_urls:
                    try:
                        r = (
                            repo_url.replace("https://github.com/", "")
                            .replace("https://www.github.com/", "")
                            .split("/")
                        )
                        repo_info: Optional[GitHubRepo] = self.extract_repo_info(
                            r[0], r[1], repo_url
                        )
                        # print(f"Found repo {repo_info}")
                        if repo_info:
                            found_repos.add(repo_info)
                    except Exception:
                        print(f"Error crawling repository: {repo_url} ")

                # Continue crawling if within depth limit
                if depth < max_depth:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        absolute_url = urljoin(current_url, href)

                        # Only crawl URLs from the same domain
                        if (
                            urlparse(absolute_url).netloc
                            == urlparse(current_url).netloc
                        ):
                            crawl(absolute_url, depth + 1)

            except RequestException as e:
                errors.append(f"Error crawling {current_url}: {str(e)}")
            except Exception as e:
                errors.append(
                    f"Unexpected error while crawling {current_url}: {str(e)}"
                )

        # Start crawling from the initial URL
        crawl(url)

        return {
            "repositories": sorted(list(found_repos), key=lambda x: x.full_url),
            "errors": errors,
        }

    def _parse_social_count(self, text: str) -> int:
        """Convert GitHub number strings to integers"""
        if not text:
            return 0

        text = text.strip().lower().replace(",", "")
        match = re.search(r"([\d.]+)([km])?", text)
        if not match:
            return 0

        number, unit = match.groups()
        value = float(number)

        if unit == "k":
            value *= 1000
        elif unit == "m":
            value *= 1000000

        return int(value)

        # """Parse numeric count from text"""
        # return int(''.join(filter(str.isdigit, text)) or 0)

    def _extract_social_counts(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Extract stars, watchers, and forks counts"""
        counts = {"stars": 0, "watchers": 0, "forks": 0}

        for link in soup.select("a.Link.Link--muted"):
            text = link.get_text(strip=True).lower()
            value = self._parse_social_count(text)

            if "star" in text:
                counts["stars"] = value
            elif "watching" in text:
                counts["watchers"] = value
            elif "fork" in text:
                counts["forks"] = value

        return counts

    def _extract_issue_counts(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Extract issues and pull requests counts"""
        counts = {"issues": 0, "pull_requests": 0}

        for link in soup.select("span.Counter"):
            parent = link.find_parent("a")
            if parent:
                href = parent.get("href", "")
                count = self._parse_social_count(link.text)

                if "/issues" in href and "pull" not in href:
                    counts["issues"] = count
                elif "/pulls" in href:
                    counts["pull_requests"] = count

        return counts

    def _parse_github_page(self, html: str) -> Dict[str, int | str | None]:
        """Parse GitHub repository page and extract all counts"""
        soup = BeautifulSoup(html, "html.parser")
        social = self._extract_social_counts(soup)
        issues = self._extract_issue_counts(soup)

        # Get repository description
        description_elem = soup.find("p", {"class": "f4"})
        description = description_elem.text.strip() if description_elem else None

        # Get last updated time
        updated_elem = soup.find("relative-time")
        last_updated = updated_elem.get("datetime") if updated_elem else None

        return {
            "stars": social["stars"],
            "watchers": social["watchers"],
            "forks": social["forks"],
            "issues": issues["issues"],
            "pull_requests": issues["pull_requests"],
            "description": description,
            "last_updated": last_updated,
        }


def get_repos(url: str) -> Dict[str, List[GitHubRepo] | List[str]]:
    extractor = GithubRepoExtractor(rate_limit_delay=1.0)
    results: List[GitHubRepo] = []
    try:
        results = extractor.extract_github_repos(url).get("repositories", [])
    except Exception as e:
        print(f"Error: {str(e)}")

    return results


def main() -> None:
    target_url = "https://contribute.cncf.io/contributors/projects/"  # Replace with your target URL

    try:
        results = get_repos(target_url)

        print(f"\nFound {len(results['repositories'])} unique GitHub repositories:")
        for repo in results["repositories"]:
            print(f"✓ {repo.owner}/{repo.repo_name}")

        if results["errors"]:
            print("\nErrors encountered:")
            for error in results["errors"]:
                print(f"✗ {error}")

    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
