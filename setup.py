from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# اقرأ الإصدار من __init__.py
version = "0.1.0"

setup(
    name="shams_cash_pulse",
    version=version,
    description="Cash Pulse - لوحة نبض النقد لمتابعة السيولة ودورة تحويل النقد في ERPNext",
    author="SHAMS SOLUTIONS",
    author_email="info@shamss.store",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
