from setuptools import setup, find_packages

version = "0.2.0"

setup(
    name="shams_cash_pulse",
    version=version,
    description="Cash Pulse - لوحة نبض النقد لمتابعة السيولة ودورة تحويل النقد في ERPNext",
    author="SHAMS SOLUTIONS",
    author_email="info@shamss.store",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],  # frappe/erpnext provided by bench; keep empty
)