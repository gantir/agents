import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time
from typing import Set, Dict, List, Optional
from requests.exceptions import RequestException
import logging
from dataclasses import dataclass

from dataclasses import dataclass

@dataclass(frozen=True)  # Making it immutable for hashability
class GitHubRepo:
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

    def __hash__(self):
        # Using full_url as the hash since it's unique for each repo
        return hash(self.full_url)
    
    def __eq__(self, other):
        if not isinstance(other, GitHubRepo):
            return NotImplemented
        return self.full_url == other.full_url

class GithubRepoExtractor:
    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; CustomBot/1.0; +http://example.com)'
        })
        
        # Refined regex pattern specifically for repositories
        # Matches pattern: github.com/owner/repo
        # Excludes: .git extensions, raw, blob, wiki, issues, pull
        self.repo_pattern = re.compile(
            r'https?://(?:www\.)?github\.com/'  # Domain
            r'([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})/'  # Owner
            r'([a-zA-Z0-9_.-]{1,100})'  # Repository name
            r'(?!/(?:raw|blob|wiki|issues|pull|releases|packages|actions))'  # Negative lookahead
            r'(?:(?:/[^\s)"\']*)?(?=$|\s|\)|\'|\"))?'  # Optional path and boundary
        )
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _parse_count(self, text: str) -> int:
        """Convert GitHub number strings to integers"""
        if not text:
            return 0
        
        text = text.strip().lower().replace(',', '')
        match = re.search(r'([\d.]+)([km])?', text)
        if not match:
            return 0
            
        number, unit = match.groups()
        value = float(number)
        
        if unit == 'k':
            value *= 1000
        elif unit == 'm':
            value *= 1000000
            
        return int(value)

    def extract_repo_info(self, owner: str, repo_name:str, repo_url:str) -> Optional[GitHubRepo]:
            
        # Skip common false positives
        if any(skip in repo_url.lower() for skip in [
            'issues', 'pull', 'wiki', 'raw', 'blob', 'tree',
            'commits', 'releases', 'packages', 'actions'
        ]):
            return None
        
        try:
            # Ensure URL is in correct format
            if not re.match(r'https?://(?:www\.)?github\.com/[\w-]+/[\w.-]+/?$', repo_url):
                raise ValueError("Invalid GitHub repository URL")

            response = self.session.get(repo_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract social counts (stars, watchers, forks)
            social_counts = {}
            for link in soup.select('a.Link.Link--muted'):
                text = link.get_text(strip=True)
                value = self._parse_count(text)
                
                if 'star' in text.lower():
                    social_counts['stars'] = value
                elif 'watching' in text.lower():
                    social_counts['watchers'] = value
                elif 'fork' in text.lower():
                    social_counts['forks'] = value

            # Extract issues and pull requests counts
            issues_count = 0
            pr_count = 0
            
            for link in soup.select('span.Counter'):
                parent = link.find_parent('a')
                if parent:
                    href = parent.get('href', '')
                    count = self._parse_count(link.text)
                    
                    if '/issues' in href and 'pull' not in href:
                        issues_count = count
                    elif '/pulls' in href:
                        pr_count = count

            # Get repository description
            description_elem = soup.find('p', {'class': 'f4'})
            description = description_elem.text.strip() if description_elem else None

            # Get last updated time
            updated_elem = soup.find('relative-time')
            last_updated = updated_elem.get('datetime') if updated_elem else None

            return GitHubRepo(
                owner=owner,
                repo_name=repo_name,
                full_url=repo_url,
                stars=social_counts.get('stars', 0),
                watchers=social_counts.get('watchers', 0),
                forks=social_counts.get('forks', 0),
                pull_requests=pr_count,
                issues=issues_count,
                description=description,
                last_updated=last_updated
            )
        except requests.exceptions.RequestException as e:
            raise RequestException(f"Failed to fetch repository data: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing repository data: {str(e)}")

    def extract_github_repos(self, url: str, max_depth: int = 1) -> Dict[str, List[GitHubRepo]]:
        """
        Crawl a webpage and extract all GitHub repository URLs.
        
        Returns:
            Dict with keys:
                'repositories': List of GitHubRepo objects
                'errors': List of error messages
        """
        visited_urls = set()
        found_repos = set()
        errors = []
        
        def crawl(current_url: str, depth: int = 0):
            if depth > max_depth or current_url in visited_urls:
                return
                
            visited_urls.add(current_url)
            
            try:
                time.sleep(self.rate_limit_delay)
                response = self.session.get(current_url, timeout=10)
                response.raise_for_status()
                
                # Find all potential repository URLs
                matches = self.repo_pattern.finditer(response.text)
                
                repo_urls = set()
                for match in matches:
                    """Extract and validate repository information from a regex match"""
                    owner, repo_name = match.groups()
                    if owner and repo_name:
                        repo_urls.add((owner, repo_name, f"https://github.com/{owner}/{repo_name}"))

                for repo_url in repo_urls:
                    try:
                        repo_info = self.extract_repo_info(repo_url[0], repo_url[1], repo_url[2])
                        print(f"Found repo {repo_info}")
                        found_repos.add(repo_info)
                    except Exception as e:
                        print(f"Error crawling repository: {repo_url} ")
                
                # Continue crawling if within depth limit
                if depth < max_depth:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        absolute_url = urljoin(current_url, href)
                        
                        # Only crawl URLs from the same domain
                        if urlparse(absolute_url).netloc == urlparse(current_url).netloc:
                            crawl(absolute_url, depth + 1)
                            
            except RequestException as e:
                errors.append(f"Error crawling {current_url}: {str(e)}")
            except Exception as e:
                errors.append(f"Unexpected error while crawling {current_url}: {str(e)}")
        
        # Start crawling from the initial URL
        crawl(url)
        
        return {
            'repositories': sorted(list(found_repos), key=lambda x: x.full_url),
            'errors': errors
        }

def main():
    """Example usage of the GitHub repository extractor"""
    extractor = GithubRepoExtractor(rate_limit_delay=1.0)
    target_url = "https://contribute.cncf.io/contributors/projects/"  # Replace with your target URL
    
    try:
        results = extractor.extract_github_repos(target_url, max_depth=1)
        
        print(f"\nFound {len(results['repositories'])} unique GitHub repositories:")
        for repo in results['repositories']:
            print(f"✓ {repo.owner}/{repo.repo_name}")
            
        if results['errors']:
            print("\nErrors encountered:")
            for error in results['errors']:
                print(f"✗ {error}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()