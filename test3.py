import requests
import pandas as pd
from datetime import datetime, timedelta
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from typing import List, Dict
import base64
import re

# Constantes
GITHUB_API = "https://api.github.com/repos/"
PYPI_API = "https://pypi.org/pypi/{}/json"
GITHUB_TOKEN = "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"  # Remplace par ton token GitHub
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

# Lecture des librairies
def read_libraries_from_file(file_path: str) -> List[str]:
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]
    
def get_github_repo_url(lib_name: str) -> str:
    try:
        response = requests.get(f"https://pypi.org/pypi/{lib_name}/json")
        if response.status_code != 200:
            return ""

        data = response.json()
        info = data.get("info", {})
        urls = info.get("project_urls", {})

        # Recherche dans les sources les plus probables
        potential_urls = [
            urls.get("Source"),
            urls.get("source"),
            urls.get("Source Code"),
            urls.get("source code"),
            urls.get("Source code"),
            urls.get("Code"),
            urls.get("Repository"),
            urls.get("repository"),
            urls.get("Github"),
            urls.get("GitHub"),
            urls.get("github"),
            urls.get("Homepage"),
            urls.get("homepage"),
            info.get("home_page")
        ]

        for url in potential_urls:
            if url and "github.com" in url:
                parts = url.split("github.com/")
                if len(parts) > 1:
                    repo = parts[1].split("/")[0:2]  # garde juste "org/repo"
                    return "/".join(repo).replace(".git", "").strip("/")
    except Exception as e:
        print(f"[Erreur GitHub Repo] {lib_name}: {e}")

    return ""

# Données PyPI
def get_pypi_data(lib_name: str) -> Dict:
    try:
        response = requests.get(PYPI_API.format(lib_name))
        if response.status_code == 200:
            data = response.json()
            info = data.get("info", {})
            releases = data.get("releases", {})
            python_target_version = Version("3.10")

            compatible_versions = []
            for version_str, release_list in releases.items():
                if not release_list:
                    continue
                if any(c in version_str for c in ['a', 'b', 'rc', 'dev']):
                    continue

                release_info = release_list[0]
                requires_python = release_info.get("requires_python", info.get("requires_python"))

                if requires_python:
                    try:
                        spec = SpecifierSet(requires_python)
                        if python_target_version in spec:
                            compatible_versions.append(version_str)
                    except:
                        continue
                else:
                    compatible_versions.append(version_str)

            try:
                sorted_versions = sorted(compatible_versions, key=Version)
                min_version = sorted_versions[0] if sorted_versions else None
                max_version = sorted_versions[-1] if sorted_versions else None
            except:
                min_version = max_version = None

            return {
                "pypi_version": info.get("version"),
                "pypi_license": info.get("license"),
                "pypi_home_page": info.get("home_page"),
                "pypi_summary": info.get("summary"),
                "pypi_requires_python": info.get("requires_python"),
                "pypi_last_release_date": releases.get(info.get("version"), [{}])[-1].get("upload_time"),
                "pypi_min_version_compatible_3_10": min_version,
                "pypi_max_version_compatible_3_10": max_version,
                "is_compatible_with_python_3_10": min_version is not None and max_version is not None
            }
    except Exception:
        pass
    return {}

# GitHub
def get_github_repo_url_bis(pypi_home_page: str) -> str:
    if pypi_home_page and "github.com" in pypi_home_page:
        parts = pypi_home_page.split("github.com/")
        try :
            return parts[1].strip("/")
        except :
            return ""
    return ""

def has_tests_in_repo(repo: str) -> bool:
    try:
        url = f"{GITHUB_API}{repo}/contents"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            for item in response.json():
                name = item.get("name", "").lower()
                if item["type"] == "dir" and name in ["tests", "test", "unittests"]:
                    return True
                if item["type"] == "file" and name.startswith("test_"):
                    return True
    except Exception:
        pass
    return False

def has_coverage_badge(repo: str) -> bool:
    try:
        response = requests.get(f"{GITHUB_API}{repo}/readme", headers=HEADERS)
        if response.status_code == 200:
            content = base64.b64decode(response.json()["content"]).decode("utf-8")
            return re.search(r'(coveralls|codecov|coverage)', content, re.IGNORECASE) is not None
    except Exception:
        pass
    return False

def get_github_data(repo: str) -> Dict:
    try:
        repo_response = requests.get(GITHUB_API + repo, headers=HEADERS)
        contributors_response = requests.get(GITHUB_API + repo + "/contributors", headers=HEADERS)
        issues_response = requests.get(GITHUB_API + repo + "/issues", headers=HEADERS, params={"state": "open"})
        print(repo_response.status_code)
        if repo_response.status_code == 200:
            repo_data = repo_response.json()
            last_commit = datetime.strptime(repo_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            contributors = contributors_response.json() if contributors_response.status_code == 200 else []
            issues = issues_response.json() if issues_response.status_code == 200 else []

            issue_response_times = []
            for issue in issues:
                if "created_at" in issue and "updated_at" in issue:
                    created = datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                    updated = datetime.strptime(issue["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
                    issue_response_times.append((updated - created).days)

            avg_response_time = round(sum(issue_response_times) / len(issue_response_times), 2) if issue_response_times else None

            return {
                "github_stars": repo_data.get("stargazers_count"),
                "github_forks": repo_data.get("forks_count"),
                "github_watchers": repo_data.get("subscribers_count"),
                "github_last_commit": last_commit,
                "github_open_issues": repo_data.get("open_issues_count"),
                "github_contributors": len(contributors),
                "github_avg_issue_response_time_days": avg_response_time,
                "has_tests": has_tests_in_repo(repo),
                "coverage_badge": has_coverage_badge(repo)
            }
    except Exception:
        pass
    return {}

# Détection crypto/web
def enrich_flags(df):
    crypto_keywords = ["bitcoin", "blockchain", "ethereum", "crypto", "web3", "wallet", "defi"]
    web_exposer_keywords = ["streamlit", "gradio", "flaskrun", "serve app", "web ui", "http server", "server", "application", "front", "api", "web"]

    def detect_keywords(text, keywords):
        if not text:
            return False
        try :
            return any(kw in text.lower() for kw in keywords)
        except :
            return False

    df["is_crypto_related"] = df.apply(
        lambda r: detect_keywords(r["library"], crypto_keywords) or
                  detect_keywords(r.get("pypi_summary", ""), crypto_keywords) or
                  detect_keywords(r.get("pypi_home_page", ""), crypto_keywords),
        axis=1
    )

    df["is_web_exposer"] = df.apply(
        lambda r: detect_keywords(r["library"], web_exposer_keywords) or
                  detect_keywords(r.get("pypi_summary", ""), web_exposer_keywords) or
                  detect_keywords(r.get("pypi_home_page", ""), web_exposer_keywords),
        axis=1
    )

    return df

# Analyse principale
def analyze_libraries(lib_list: List[str]) -> pd.DataFrame:
    results = []
    count = 0
    for lib in lib_list:
        print("lib : ", lib)
        pypi_info = get_pypi_data(lib)
        github_repo = get_github_repo_url(lib)
        github_info = get_github_data(github_repo) if github_repo else {}
        print(count)
        print(github_repo)
        print(github_info)

        results.append({ "library": lib, **pypi_info, **github_info })
        count += 1

    df = pd.DataFrame(results)
    df = enrich_flags(df)
    return df

# Main
if __name__ == "__main__":
    libraries_to_check = read_libraries_from_file("lib.txt")
    df_result = analyze_libraries(libraries_to_check)
    df_result.to_csv("library_audit.csv", index=False)
    print(df_result.columns.tolist())
    print(df_result.head(3))

