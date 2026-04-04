import pandas as pd
import numpy as np
import random
from datetime import date, timedelta

np.random.seed(42)

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))

def generate_employee_data(rows, file_name):
    basic = np.random.randint(4000, 30000, rows)
    hra = (basic * 0.30).astype(int)
    other = np.random.randint(500, 3000, rows)
    individual = np.random.randint(0, 2000, rows)
    ot = np.random.randint(0, 1500, rows)

    fixed = basic + hra + other + individual + ot

    vehicle = np.random.randint(0, 2000, rows)
    telephone = np.random.randint(0, 800, rows)
    special = np.random.randint(0, 1500, rows)
    salik = np.random.randint(0, 500, rows)
    travel = np.random.randint(0, 1200, rows)

    tgs = fixed + vehicle + telephone + special + salik + travel

    increment = (basic * np.random.uniform(0.03, 0.12, rows)).astype(int)
    new_basic = basic + increment
    new_hra = (new_basic * 0.30).astype(int)
    new_fixed = new_basic + new_hra + other + individual + ot
    new_tgs = new_fixed + vehicle + telephone + special + salik + travel

    df = pd.DataFrame({
        "S. No": range(1, rows + 1),
        "E Code": [f"E{100000 + i}" for i in range(rows)],
        "Name": [f"Employee_{i}" for i in range(1, rows + 1)],
        "Band": np.random.choice(list("ABCDE"), rows),
        "Designation": np.random.choice(
            ["Analyst", "Senior Analyst", "Manager", "Senior Manager", "Director"], rows
        ),
        "Vertical": np.random.choice(["IT", "Finance", "HR", "Operations", "Sales"], rows),
        "Currency": ["AED"] * rows,
        "Business Unit": np.random.choice(["UAE", "KSA", "Qatar", "Oman"], rows),
        "Department": np.random.choice(
            ["Development", "Support", "Accounts", "Admin", "Marketing"], rows
        ),
        "Performance year": np.random.choice([2022, 2023, 2024], rows),
        "Rating Label": np.random.choice(
            ["Outstanding", "Exceeds", "Meets", "Below"], rows
        ),
        "Promotion": np.random.choice(["Yes", "No"], rows),
        "New Designation": np.random.choice(
            ["Analyst", "Senior Analyst", "Manager", "Senior Manager", "Director"], rows
        ),
        "New Role Band": np.random.choice(list("ABCDE"), rows),
        "AED Per Month": np.random.randint(0, 5000, rows),
        "Organizational Allowance": np.random.randint(0, 3000, rows),
        "Next Review Date": [
            random_date(date(2025, 1, 1), date(2026, 12, 31))
            for _ in range(rows)
        ],
        "New salary effective date": [
            random_date(date(2024, 1, 1), date(2025, 12, 31))
            for _ in range(rows)
        ],
        "New salary effective Year": np.random.choice([2024, 2025], rows),
        "Current Basic Salary": basic,
        "Current HRA": hra,
        "Current Other Allowances": other,
        "Current Individual Allowances": individual,
        "Current Compulsory OT": ot,
        "Current Fixed Salary (A)": fixed,
        "Current Vehicle Allowance": vehicle,
        "Current Telephone Allowance": telephone,
        "Current Special Allowances": special,
        "Current Salik Allowance": salik,
        "Current Travel & Mobile Allowance (B)": travel,
        "Current Total Gross Salary (TGS) (A) + (B)": tgs,
        "New Basic Salary": new_basic,
        "New HRA": new_hra,
        "New Other Allowances": other,
        "New Individual Allowances": individual,
        "New Compulsory OT": ot,
        "New Fixed Salary (A,)": new_fixed,
        "New Vehicle Allowance": vehicle,
        "New Telephone Allowance": telephone,
        "New Special Allowances": special,
        "New Salik Allowance": salik,
        "New Travel & Mobile Allowance (B)": travel,
        "New Total Gross Salary (TGS) (A) + (B)": new_tgs,
        "PIP Duration": np.random.choice(["", "3 Months", "6 Months"], rows),
        "PIP Effective Date": [
            random_date(date(2024, 1, 1), date(2025, 12, 31))
            for _ in range(rows)
        ],
        "Letter type": np.random.choice(
            [
                "rating_increment_oa_less_than_10k", #Rating + Increment + OA _3installments
                "rating_increment_oa_more_than_10k", #Rating Only
                "rating_increment_promotion_oa_less_than_10k", #Rating+ Increment
                "rating_increment_promotion_oa_more_than_10k", #Rating+ Increment + OA_Less than 10k
                "rating_increment_promotion", #Rating+ Increment + OA_Less than 10k
                "rating_increment", #Rating+ Increment + OA_Less than 10k
                "rating_oa_less_than_10K", #Rating+ Increment + OA_Less than 10k
                "rating_oa_more_than_10K", #Rating+ Increment + OA_Less than 10k
                "rating", #Rating+ Increment + OA_Less than 10k
                "PIP"

            ],
            rows,
        ),
        "Signatory Designation": np.random.choice(
            ["HR Manager", "HR Director", "CEO"], rows
        ),
        "Signatory Name": np.random.choice(
            ["A. Khan", "M. Ali", "S. Patel", "R. Thomas"], rows
        ),
    })

    df.to_excel(file_name, index=False)
    print(f"✅ File created: {file_name}")

# ---- Generate files ----
# generate_employee_data(10, "emp_10.xlsx")
generate_employee_data(1000, "emp_1k.xlsx")
# generate_employee_data(10000, "emp_10k.xlsx")
# generate_employee_data(70000, "emp_70k.xlsx")
