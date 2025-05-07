from setuptools import setup, find_packages

setup(
    name="finlight-client",
    version="0.5.0",
    description="Python client for the Finlight API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Ali Büyükkakac",
    author_email="ali@kakac.de",
    url="https://github.com/jubeiargh/finlight-client-py",
    packages=find_packages(),
    install_requires=["requests", "websockets>=14.0", "pydantic>=2.7,<3.0"],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
