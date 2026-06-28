from setuptools import setup, find_packages

setup(
    name="pixelos",
    version="2.0.0",
    description="PixelOS - Système de Gestion Agricole Connecté",
    author="AgriCol",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pyyaml>=6.0",
        "paho-mqtt>=1.6",
        "structlog>=23.0",
        "requests>=2.28",
        "psutil>=5.9",
    ],
    extras_require={
        "web": ["flask>=3.0", "flask-socketio>=5.3"],
        "db": ["mysql-connector-python>=8.0", "pymongo>=4.5"],
        "full": ["flask>=3.0", "flask-socketio>=5.3",
                 "mysql-connector-python>=8.0", "pymongo>=4.5"],
    },
    entry_points={
        "console_scripts": [
            "pixelos=cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
    ],
)
