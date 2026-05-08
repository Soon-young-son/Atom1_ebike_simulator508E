import streamlit as st
import pandas as pd
import math

# --- Page basic settings (Dark theme feel) ---
st.set_page_config(page_title="Atom1 E-bike Simulator", layout="wide")

# --- Physics Engine Class ---
class Atom1Controller:
    RPM_STEPS = [0, 640, 960, 1280, 1600, 1750]
    MODES = ['F', 'E', 'D', 'C', 'B', 'A']
    
    WHEEL_TORQUE_MAP = {
        640:  {'A':4, 'B':4, 'C':4, 'D':4, 'E':4, 'F':4},
        960:  {'A':6, 'B':5, 'C':4, 'D':4, 'E':4, 'F':4},
        1280: {'A':8, 'B':6, 'C':5, 'D':3, 'E':3, 'F':2},
        1600: {'A':10, 'B':7, 'C':5, 'D':4, 'E':3, 'F':2},
        1750: {'A':10, 'B':7, 'C':6, 'D':4, 'E':3, 'F':1}
    }
    
    # Current per mode (for display)
    CURRENT_MAP = {
        640:  {'A':6.94, 'B':6.94, 'C':6.94, 'D':6.94, 'E':6.94, 'F':6.94},
        960:  {'A':6.94, 'B':6.94, 'C':6.00, 'D':5.00, 'E':4.00, 'F':3.00},
        1280: {'A':6.94, 'B':6.00, 'C':5.00, 'D':4.00, 'E':3.00, 'F':2.00},
        1600: {'A':6.94, 'B':5.00, 'C':4.00, 'D':3.00, 'E':2.00, 'F':1.50},
        1750: {'A':6.94, 'B':5.00, 'C':4.00, 'D':3.00, 'E':2.00, 'F':1.00}
    }

    def simulate_state(self, target_rpm, mode_idx, slope_percent, rider_torque):
        if target_rpm == 0:
            return {"Mode": "-", "Current": 0, "Actual RPM": 0, "Speed": 0, "Req Torque": 0, "Avail Torque": 0}

        map_rpm = min(self.RPM_STEPS[1:], key=lambda k: abs(k - target_rpm))
        active_mode = self.MODES[mode_idx]
        
        motor_torque = self.WHEEL_TORQUE_MAP[map_rpm][active_mode]
        avail_torque = motor_torque + rider_torque
        
        angle_rad = math.atan(slope_percent / 100.0)
        req_torque = (90.0 * 9.81 * math.sin(angle_rad) * 0.254) + 2.0

        # RPM calculation based on torque difference
        if avail_torque < req_torque:
            actual_rpm = target_rpm * (avail_torque / req_torque)
        else:
            surge = min(0.15, (avail_torque - req_torque) / max(1.0, avail_torque))
            actual_rpm = target_rpm * (1.0 + surge)

        ring_rpm = actual_rpm / 32.0
        chainring_rpm = (3 * 50) + (2 * ring_rpm)
        speed_kmh = (chainring_rpm * (20.0 / 28.0)) * 0.09576 

        return {
            "Mode": active_mode, 
            "Current": self.CURRENT_MAP[map_rpm][active_mode],
            "Actual RPM": int(actual_rpm),
            "Speed": round(speed_kmh, 1),
            "Req Torque": req_torque, 
            "Avail Torque": avail_torque
        }

# --- Initialize session state ---
if 'target_rpm' not in st.session_state: st.session_state.target_rpm = 1600
if 'mode_idx' not in st.session_state: st.session_state.mode_idx = 1 # Mode E

# --- UI Layout ---
st.title("🚲 Atom1 E-bike Simulator")

# Sidebar input
st.sidebar.header("🎛️ Control Panel")
col1, col2 = st.sidebar.columns(2)
if col1.button("🔼 Step Up"):
    idx = Atom1Controller.RPM_STEPS.index(st.session_state.target_rpm)
    if idx < 5: st.session_state.target_rpm = Atom1Controller.RPM_STEPS[idx+1]
if col2.button("🔽 Step Down"):
    idx = Atom1Controller.RPM_STEPS.index(st.session_state.target_rpm)
    if idx > 1: st.session_state.target_rpm = Atom1Controller.RPM_STEPS[idx-1]

slope = st.sidebar.slider("Slope (%)", 0, 15, 4)
rider_tq = st.sidebar.slider("Rider Torque (Nm)", 0, 15, 4)

# Execute physics engine and process auto-shifting logic
bike = Atom1Controller()
state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)

# Auto-shifting simulation (change mode until state stabilizes)
for _ in range(5):
    if state['Actual RPM'] <= st.session_state.target_rpm * 0.90:
        if st.session_state.mode_idx < 5: 
            st.session_state.mode_idx += 1
            state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)
    elif state['Actual RPM'] >= st.session_state.target_rpm * 1.10:
        if st.session_state.mode_idx > 0:
            st.session_state.mode_idx -= 1
            state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)

# --- Output Results ---
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Speed (km/h)", f"{state['Speed']}")
m2.metric("Driving Mode", f"{state['Mode']}")
m3.metric("Supplied Current (A)", f"{state['Current']} A")
m4.metric("Target RPM", f"{st.session_state.target_rpm}")
m5.metric("Actual RPM", f"{state['Actual RPM']}")

st.divider()

# --- Torque Balance Graph ---
st.subheader("📊 Torque Balance (Required vs Supplied)")
chart_data = pd.DataFrame({
    "Category": ["Required Torque (Slope Resistance)", "Supplied Torque (Motor + Rider)"],
    "Torque (Nm)": [state['Req Torque'], state['Avail Torque']]
})
st.bar_chart(chart_data.set_index("Category"), color=["#ff4b4b"])

if state['Req Torque'] > state['Avail Torque']:
    st.warning(f"⚠️ Supplied torque is insufficient, actual RPM has dropped below the target! (Current Mode: {state['Mode']})")
else:
    st.success(f"✅ Supplied torque is sufficient, stably maintaining/accelerating to target RPM.")
