from setuptools import setup, find_packages

setup(
    name="finlight-client",
    version="0.1.0",
    description="Python client for the Finlight API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="ali@kakac.de",
    url="https://github.com/jubeiargh/finlight-client-py",
    packages=find_packages(),
    install_requires=[
        "requests",
        "websocket-client",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
