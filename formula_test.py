def calculate_risk(C, S, D7, P, E):
    # C = Current Stock
    # S = Safety Stock
    # D7 = Predicted 7-day Demand
    # P = Pending Requests
    # E = Expected Donations

    net_demand = D7 + P
    net_supply = C + E

    # 1. Supply-Demand Gap (Max 50 points)
    # If supply covers 150% of demand -> 0 risk
    # If supply covers 100% of demand -> 20 risk
    # If supply covers 50% of demand -> 40 risk
    # If supply covers 0% of demand -> 50 risk
    if net_demand == 0:
        gap_score = 0
    else:
        ratio = net_supply / net_demand
        if ratio >= 1.5:
            gap_score = 0
        elif ratio >= 1.0:
            # maps 1.0-1.5 to 20-0
            gap_score = 20 * (1.5 - ratio) / 0.5
        else:
            # maps 0.0-1.0 to 50-20
            gap_score = 20 + 30 * (1.0 - ratio)

    # 2. Safety Stock Breach (Max 30 points)
    # If current stock covers 150% of safety -> 0 risk
    # If current stock covers 100% of safety -> 10 risk
    # If current stock covers 0% of safety -> 30 risk
    if S == 0:
        safety_score = 0
    else:
        s_ratio = C / S
        if s_ratio >= 1.5:
            safety_score = 0
        elif s_ratio >= 1.0:
            # maps 1.0-1.5 to 10-0
            safety_score = 10 * (1.5 - s_ratio) / 0.5
        else:
            # maps 0.0-1.0 to 30-10
            safety_score = 10 + 20 * (1.0 - s_ratio)

    # 3. Days to Depletion / Trend (Max 20 points)
    daily_consumption = net_demand / 7.0 if net_demand > 0 else 0
    if daily_consumption == 0:
        trend_score = 0
    else:
        dio = net_supply / daily_consumption
        if dio >= 7:
            trend_score = 0
        else:
            # maps 0-7 days to 20-0
            trend_score = 20 * (1.0 - dio / 7.0)

    # Overrides
    if C == 0:
        total_score = 100
    else:
        total_score = int(gap_score + safety_score + trend_score)
        
    total_score = min(100, max(0, total_score))
    
    if total_score <= 20:
        level = 'HEALTHY'
    elif total_score <= 40:
        level = 'LOW'
    elif total_score <= 60:
        level = 'MODERATE'
    elif total_score <= 80:
        level = 'HIGH RISK'
    else:
        level = 'CRITICAL'
        
    return total_score, level, gap_score, safety_score, trend_score

test_cases = [
    ("A+  ", 66, 50, 69, 0, 0),
    ("O+  ", 57, 60, 82, 0, 0),
    ("O-  ", 23, 20, 29, 0, 0),
    ("B-  ", 4,  2,  1,  0, 0),
    ("A-  ", 6,  3,  7,  0, 0),
    ("AB- ", 1,  1,  1,  0, 0),
    ("EMPTY", 0, 10, 5, 0, 0),
    ("SAFE", 100, 20, 10, 0, 0)
]

print("Type | C | S | D7 | R_Score | Level | Gap | Safety | Trend")
for name, c, s, d7, p, e in test_cases:
    score, lvl, g, saf, t = calculate_risk(c, s, d7, p, e)
    print(f"{name} | {c:2d} | {s:2d} | {d7:2d} | {score:3d} | {lvl:9s} | {g:4.1f} | {saf:4.1f} | {t:4.1f}")
