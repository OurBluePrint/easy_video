from setuptools import setup, find_packages

setup(
    name="easy_video",
    version="0.2",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "psutil",
        "tqdm"
    ],
)