from __future__ import annotations
from .models import SliceType, HospitalDevice


def build_devices() -> list[HospitalDevice]:
    """Return all hospital IoT/medical devices across three network slices."""
    return [
        # ── Slice A · URLLC · Critical Care ──────────────────────────────────
        HospitalDevice("icu_1",      "ICU Monitor 1",       "ICU",         SliceType.URLLC, "10.0.1.1", "vital_signs",      10,   128),
        HospitalDevice("icu_2",      "ICU Monitor 2",       "ICU",         SliceType.URLLC, "10.0.1.2", "vital_signs",      10,   128),
        HospitalDevice("surg_robot", "Surgical Robot",      "Operating Rm",SliceType.URLLC, "10.0.2.1", "surgical_control", 50,    64),
        HospitalDevice("emerg",      "Emergency Alert Sys", "Emergency",   SliceType.URLLC, "10.0.3.1", "icu_alert",         2,    32),

        # ── Slice B · mIoT · Sensor Network ──────────────────────────────────
        HospitalDevice("wear_1",     "Wearable Monitor 1",  "Ward A",      SliceType.mIoT,  "10.1.1.1", "wearable_data",     2,    64),
        HospitalDevice("wear_2",     "Wearable Monitor 2",  "Ward B",      SliceType.mIoT,  "10.1.1.2", "wearable_data",     2,    64),
        HospitalDevice("temp_sens",  "Temp/Humidity Sensor","Ward A",      SliceType.mIoT,  "10.1.2.1", "env_sensor",       0.5,   32),
        HospitalDevice("bed_sens",   "Bed Occupancy Sensor","Ward B",      SliceType.mIoT,  "10.1.2.2", "bed_sensor",       0.2,   32),
        HospitalDevice("infusion",   "Smart Infusion Pump", "Ward C",      SliceType.mIoT,  "10.1.2.3", "infusion_data",     1,    64),

        # ── Slice C · eMBB · General Network ─────────────────────────────────
        HospitalDevice("staff_tab",  "Staff Tablet",        "Nurses Stn.", SliceType.eMBB,  "10.2.1.1", "staff_comm",        5,   512),
        HospitalDevice("admin_pc",   "Admin PC",            "Admin Office",SliceType.eMBB,  "10.2.2.1", "admin_data",        3,  1024),
        HospitalDevice("guest_ap",   "Guest WiFi AP",       "Lobby",       SliceType.eMBB,  "10.2.2.2", "guest_traffic",     8,  1500),
        HospitalDevice("mri_up",     "MRI Upload Station",  "Radiology",   SliceType.eMBB,  "10.2.2.3", "imaging_data",      1,  8192),
    ]


TOPOLOGY_INFO = {
    "controller": {"id": "c0", "type": "RYU SDN Controller", "protocol": "OpenFlow 1.3"},
    "switches": [
        {"id": "s0", "name": "Core Switch",  "role": "aggregation"},
        {"id": "s1", "name": "URLLC Switch", "slice": "A"},
        {"id": "s2", "name": "mIoT Switch",  "slice": "B"},
        {"id": "s3", "name": "eMBB Switch",  "slice": "C"},
    ],
    "edge_nodes": [
        {"id": "e0", "name": "ICU Edge Node",  "slice": "A", "desc": "Instant alert generation"},
        {"id": "e1", "name": "IoT Edge Node",  "slice": "B", "desc": "Sensor data aggregation"},
    ],
}
