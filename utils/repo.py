import os
import subprocess
import requests
from git import Repo

# Function to check if a repo is approved
def is_repo_approved(repo_url):
    # Replace with actual logic to check if the repo is approved
    # For example, querying a database or a list of approved repos
    approved_repos = [
        "https://github.com/user/repo1",
        "https://github.com/user/repo2"
    ]
    return repo_url in approved_repos

# Function to safely clone a GitHub repository
def clone_repo(repo_url, destination):
    """
    Clones a GitHub repository if it is approved.
    
    Args:
    repo_url (str): The URL of the GitHub repository to clone.
    destination (str): The local path where the repository should be cloned.
    
    Returns:
    bool: True if the repository was cloned successfully, False otherwise.
    """
    # Check if the repo is approved
    if not is_repo_approved(repo_url):
        print(f"Repository {repo_url} is not approved.")
        return False
    
    # Check if the destination directory already exists
    if os.path.exists(destination):
        print(f"Destination directory {destination} already exists.")
        return False
    
    try:
        # Clone the repository
        Repo.clone_from(repo_url, destination)
        print(f"Repository {repo_url} cloned successfully to {destination}.")
        return True
    except Exception as e:
        print(f"Failed to clone repository {repo_url}: {e}")
        return False

# Example usage
if __name__ == "__main__":
    repo_url = "https://github.com/user/repo1"
    destination = "/path/to/local/repo"
    clone_repo(repo_url, destination)