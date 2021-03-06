from setuptools import setup, find_packages
from codecs import open

setup(
    name='seedbank',
    version='0.0.1',
    description='Seedbank is a librarian for your Amazon Glacier archives',
    author='Caleb Foust',
    author_email='cfoust@sqweebloid.com',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'GitPython',
        'boto3', 
        'click',
        'jsondate'
    ],
    entry_points="""
        [console_scripts]
        sb=seedbank.cli:cli
        """,
)
