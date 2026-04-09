from setuptools import setup, find_packages

setup(
    name="ntfs-toolkit",
    version="3.0.1",
    description="NTFS forensics, low-level disk analysis, and education toolkit",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Ibrahim Isleem",
    author_email="ibrahimtarekeslim@gmail.com",
    license="MIT",
    url="https://github.com/IbrahimTEslim/LBALab",
    packages=find_packages(include=["ntfs_toolkit*"]),
    python_requires=">=3.8",
    install_requires=["rich>=13.0"],
    entry_points={
        "console_scripts": [
            "ntfs-toolkit=ntfs_toolkit.explorer.cli:main",
            "ntfs-learn=ntfs_toolkit.learn.runner:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Topic :: Security",
        "Topic :: System :: Filesystems",
        "Topic :: Education",
    ],
)
