from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="NanoSwap-Meta-Pools",
    description="Metapool AMM",
    author="Yann Long",
    version="1.0",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    project_urls={
        "Source": "https://github.com/YannLong17/NanoSwap-Meta-Pools",
    },
    # install_requires=["algofi-amm-py-sdk==1.0.5"],
    packages=find_packages(),
    python_requires=">=3.7",
    include_package_data=True,
)
