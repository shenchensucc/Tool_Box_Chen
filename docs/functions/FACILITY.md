# 🏭 Facility Tools - Development Guide

## 📍 Function Location

- **Frontend**: `frontend/pages/` (sidebar section Facility)
  - TML Data Loader: `frontend/pages/2_TML_Data_Loader.py`
  - De-active CML: `frontend/pages/7_Deactive_CML.py`
- **Backend**: `backend/tml/` (TML processing modules)

---

## 🎯 Function Purpose

The **Facility Tools** will provide:
1. Facility data management
2. Equipment tracking
3. Maintenance scheduling
4. Performance analysis
5. Reporting and visualization

**Current Status**: Placeholder page

---

## 🏗️ Current Implementation

### Current Structure

Facility is now an expandable sidebar section containing specialized tools:

**TML Data Loader** (`pages/2_TML_Data_Loader.py`)
- Processes Thickness Monitoring Location (TML) data
- Supports 20 different workflows
- Batch processing with multiple parameters
- ZIP file output with all results

**De-active CML** (`pages/7_Deactive_CML.py`)
- Single-upload tool to deactivate all CMLs in a sheet
- Optional template (uses default TM_Loader_Template.xlsx if not provided)
- Flexible column naming and auto-detect sheet (tries Source_Data, then any sheet with required columns)
- Detailed error display for debugging (status code, endpoint, full detail)
- Output: `{filename}_deactive.xlsx` with Status Indicator = "Inactive"

### Status

- ✅ Facility section exists as expandable sidebar
- ✅ TML Data Loader fully implemented
- ✅ De-active CML fully implemented
- ✅ Backend integration complete
- ❌ Additional facility tools planned

---

## 🔮 Planned Features

### Phase 1: Basic Facility Management

**Priority**: High  
**Effort**: 1-2 weeks

1. **Facility Registry**
   - Add/edit/delete facilities
   - Basic info (name, location, type, capacity)
   - Upload facility documents

2. **Equipment List**
   - Equipment inventory per facility
   - Equipment details (type, model, serial number)
   - Status tracking (operational, maintenance, offline)

3. **Simple Dashboard**
   - Facility count
   - Equipment status summary
   - Recent activity

**Backend Requirements**:
- Database tables for facilities and equipment
- CRUD endpoints for facilities
- CRUD endpoints for equipment

### Phase 2: Maintenance Management

**Priority**: Medium  
**Effort**: 2-3 weeks

1. **Maintenance Scheduling**
   - Schedule preventive maintenance
   - Track maintenance history
   - Assign to technicians

2. **Work Orders**
   - Create work orders
   - Track status (pending, in-progress, completed)
   - Record completion details

3. **Notifications**
   - Upcoming maintenance alerts
   - Overdue maintenance warnings
   - Equipment status changes

**Backend Requirements**:
- Maintenance schedule tables
- Work order management endpoints
- Notification system

### Phase 3: Performance Analysis

**Priority**: Low  
**Effort**: 2-3 weeks

1. **Performance Metrics**
   - Uptime tracking
   - Maintenance frequency
   - Cost analysis

2. **Visualizations**
   - Performance trends
   - Comparison charts
   - Downtime analysis

3. **Reporting**
   - Generate PDF reports
   - Export to Excel
   - Scheduled reports

**Backend Requirements**:
- Performance calculation endpoints
- Report generation service
- Data aggregation

---

## 🔧 Development Approach

### Step 1: Define Data Models

```python
# backend/models.py

class Facility(BaseModel):
    """Facility data model"""
    id: int
    name: str
    location: str
    facility_type: str  # e.g., "processing", "storage", "pumping"
    capacity: Optional[float]
    status: str  # "operational", "maintenance", "offline"
    created_at: datetime
    updated_at: datetime

class Equipment(BaseModel):
    """Equipment data model"""
    id: int
    facility_id: int
    name: str
    equipment_type: str
    model: str
    serial_number: str
    installation_date: date
    status: str  # "operational", "maintenance", "offline"
    last_maintenance: Optional[date]
    next_maintenance: Optional[date]

class MaintenanceRecord(BaseModel):
    """Maintenance record"""
    id: int
    equipment_id: int
    maintenance_date: date
    maintenance_type: str  # "preventive", "corrective", "inspection"
    performed_by: str
    notes: str
    cost: Optional[float]
```

### Step 2: Implement Backend Endpoints

```python
# backend/main.py

# Facility endpoints
@app.get("/api/facilities", response_model=List[Facility])
async def list_facilities():
    """List all facilities"""
    pass

@app.post("/api/facilities", response_model=Facility)
async def create_facility(facility: Facility):
    """Create new facility"""
    pass

@app.get("/api/facilities/{facility_id}", response_model=Facility)
async def get_facility(facility_id: int):
    """Get facility by ID"""
    pass

@app.put("/api/facilities/{facility_id}", response_model=Facility)
async def update_facility(facility_id: int, facility: Facility):
    """Update facility"""
    pass

@app.delete("/api/facilities/{facility_id}")
async def delete_facility(facility_id: int):
    """Delete facility"""
    pass

# Equipment endpoints
@app.get("/api/facilities/{facility_id}/equipment", response_model=List[Equipment])
async def list_equipment(facility_id: int):
    """List equipment for a facility"""
    pass

# ... more endpoints
```

### Step 3: Build Frontend UI

```python
# frontend/pages/Facility/ (expandable section)
# Example for future tools:

import streamlit as st
from frontend_utils import (
    list_facilities,
    create_facility,
    update_facility,
    delete_facility
)

st.title("🏭 Facility Tools")

# Tabs for different functions
tab1, tab2, tab3 = st.tabs(["Facilities", "Equipment", "Maintenance"])

with tab1:
    st.subheader("Facility Management")
    
    # List facilities
    facilities = list_facilities()
    for facility in facilities:
        with st.expander(facility['name']):
            st.write(f"Location: {facility['location']}")
            st.write(f"Type: {facility['facility_type']}")
            st.write(f"Status: {facility['status']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Edit", key=f"edit_{facility['id']}"):
                    # Show edit form
                    pass
            with col2:
                if st.button("Delete", key=f"delete_{facility['id']}"):
                    delete_facility(facility['id'])
                    st.experimental_rerun()
    
    # Add new facility
    with st.form("new_facility"):
        st.subheader("Add New Facility")
        name = st.text_input("Facility Name")
        location = st.text_input("Location")
        facility_type = st.selectbox("Type", ["Processing", "Storage", "Pumping"])
        capacity = st.number_input("Capacity", min_value=0.0)
        
        if st.form_submit_button("Create Facility"):
            create_facility({
                "name": name,
                "location": location,
                "facility_type": facility_type,
                "capacity": capacity,
                "status": "operational"
            })
            st.success("Facility created!")
            st.experimental_rerun()

with tab2:
    st.subheader("Equipment Management")
    st.info("Select a facility to view equipment")
    # ... equipment management UI

with tab3:
    st.subheader("Maintenance Scheduling")
    st.info("Maintenance features coming soon")
    # ... maintenance UI
```

---

## 🚨 CRITICAL: Before Implementation

### Must-Read Documents

1. **`docs/AI_DEVELOPMENT_RULES.md`**
   - Ensure changes are scoped correctly
   - Don't modify other functions

2. **`docs/ARCHITECTURE.md`**
   - Understand database requirements
   - Plan data models carefully

3. **`docs/CODE_REVIEW_CHECKLIST.md`**
   - Follow security guidelines
   - Implement proper validation

### Database Considerations

**Before implementing facility tools, decide**:

1. **Database choice**: PostgreSQL, SQLite, or other?
2. **ORM**: SQLAlchemy, Tortoise, or raw SQL?
3. **Migrations**: Alembic for schema changes?
4. **Authentication**: User accounts required?

**Recommendation**: Start with SQLite for development, plan migration to PostgreSQL for production.

---

## 🧪 Testing Strategy

### Phase 1 Tests

```python
# tests/test_facility.py

def test_create_facility():
    """Test facility creation"""
    response = client.post("/api/facilities", json={
        "name": "Test Facility",
        "location": "Test Location",
        "facility_type": "processing",
        "status": "operational"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Test Facility"

def test_list_facilities():
    """Test listing facilities"""
    response = client.get("/api/facilities")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_facility():
    """Test facility update"""
    # Create facility first
    create_response = client.post("/api/facilities", json={...})
    facility_id = create_response.json()["id"]
    
    # Update facility
    response = client.put(f"/api/facilities/{facility_id}", json={
        "name": "Updated Name",
        ...
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"

def test_delete_facility():
    """Test facility deletion"""
    # Create then delete
    ...
```

---

## 📋 Implementation Checklist

### Planning Phase

- [ ] Read all relevant documentation
- [ ] Design database schema
- [ ] Define API endpoints
- [ ] Create mockups/wireframes
- [ ] Get approval for design

### Development Phase

- [ ] Create data models (`backend/models.py`)
- [ ] Set up database tables
- [ ] Implement CRUD endpoints
- [ ] Write endpoint tests
- [ ] Create frontend UI
- [ ] Implement API calls (`frontend_utils.py`)
- [ ] Manual testing

### Documentation Phase

- [ ] Update this guide with implementation details
- [ ] Document API endpoints in `BACKEND_API.md`
- [ ] Update main `README.md` with new features
- [ ] Add usage examples

### Review Phase

- [ ] Code review using `CODE_REVIEW_CHECKLIST.md`
- [ ] Security review
- [ ] Performance testing
- [ ] User acceptance testing

---

## 🔗 Related Documentation

- [BACKEND_API.md](BACKEND_API.md) - How to add new endpoints
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
- [DEVELOPMENT_GUIDE.md](../DEVELOPMENT_GUIDE.md) - Development practices
- [CODE_REVIEW_CHECKLIST.md](../CODE_REVIEW_CHECKLIST.md) - Review standards

---

## 💡 Implementation Tips

### Start Small

Begin with minimal viable features:
1. Add one facility
2. List facilities
3. View facility details

Then iterate to add more features.

### Reuse Patterns

- Copy structure from ILI Visual Tool
- Reuse API patterns from existing endpoints
- Follow established Streamlit layouts

### Think About Scale

- Design for multiple users from start
- Consider data volume (100s of facilities? 1000s?)
- Plan for search/filter capabilities

---

**Last Updated**: October 2025  
**Status**: Not yet implemented - ready for development
