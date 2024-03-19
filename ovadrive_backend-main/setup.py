# Import necessary modules
from setuptools import find_packages, setup

# Read the README file to use as long description
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Define the package version
__version__ = "1.0.0"

# Define project-specific variables
REPO_NAME = "ovadrive_backend"
AUTHOR_USER_NAME = 'FlicLabs'
SRC_REPO = 'Ovadrive'
AUTHOR_EMAIL = "persistventures007@gmail.com"

# Setup configuration
setup(
    name=SRC_REPO,
    version=__version__,
    author=AUTHOR_USER_NAME,
    author_email=AUTHOR_EMAIL,
    description="Personal AI assistant for keeping daily track records.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=(f'https://github.com/{AUTHOR_USER_NAME}/{REPO_NAME}'),
    project_urls={"Bug Tracker": f'https://github.com/{AUTHOR_USER_NAME}/{REPO_NAME}/issues'},
    package_dir={"": "src"},
    packages=find_packages(where="src")
)