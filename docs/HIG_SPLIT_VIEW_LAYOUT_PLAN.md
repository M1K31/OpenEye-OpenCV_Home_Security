# OpenEye UI Layout Enhancement Plan
## HIG Split View Architecture Implementation
### Version: 3.5.2-planned
### Date: October 12, 2025

---

## 🎯 Overview

This document outlines the planned transformation of OpenEye's UI from the current page-based navigation to a modern Apple Human Interface Guidelines (HIG) Split View architecture with persistent sidebar navigation.

---

## 📐 Current Architecture

### Current Navigation Pattern
- **Dashboard** - Main page with header buttons
- **Settings Page** - Tabbed interface with embedded sub-pages
- **Individual Pages** - Standalone pages with "Back to Dashboard" buttons

### Current Issues
1. Navigation requires clicking through multiple pages
2. No persistent global navigation
3. Camera feeds hidden when accessing settings
4. Context switching disrupts monitoring workflow

---

## 🏗️ Proposed Architecture

### HIG Split View Structure

```
┌─────────────────────────────────────────────────────────┐
│  [OpenEye Logo/Title]          [Status] [User] [Logout] │ ← Top Bar
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│  🏠      │                                              │
│  Live    │                                              │
│          │         MAIN CONTENT AREA                    │
│  🚨      │         (Dynamic based on sidebar          │
│  Events  │          selection)                          │
│          │                                              │
│  📹      │                                              │
│  Cameras │                                              │
│          │                                              │
│  👤      │                                              │
│  AI &    │                                              │
│  Faces   │                                              │
│          │                                              │
│  ⚙️      │                                              │
│  System  │                                              │
│  Settings│                                              │
│          │                                              │
│  🎨      │                                              │
│  Themes  │                                              │
│          │                                              │
Sidebar    │              Content Pane                    │
(Fixed)    │              (Scrollable)                    │
└──────────┴──────────────────────────────────────────────┘
```

---

## 📊 Navigation Structure

### Primary Sidebar Sections

| Icon | Section | Content | Priority |
|------|---------|---------|----------|
| 🏠 | Live Dashboard | Real-time camera feeds, global status, event timeline | **High** |
| 🚨 | Events & History | Motion/face alerts, video playback, filtering | **High** |
| 📹 | Camera Manager | Camera config, discovery, per-camera settings | **Medium** |
| 👤 | AI & Faces | Face recognition, known faces, AI settings | **Medium** |
| ⚙️ | System & Alerts | Global settings, notifications, integrations | **Medium** |
| 🎨 | Themes | Theme selector (quick access) | **Low** |

---

## 🎨 Aqua Security Theme Integration

### Liquid Glass Sidebar

```css
.sidebar {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}
```

### Content Pane

```css
.content-pane {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 20px;
}
```

---

## 🔄 Component Refactoring Plan

### Phase 1: Create Layout Components

#### 1. `MainLayout.jsx` - Master Container
```jsx
<MainLayout>
  <Sidebar currentSection={section} onNavigate={handleNav} />
  <ContentPane>
    {renderSectionContent(section)}
  </ContentPane>
</MainLayout>
```

#### 2. `Sidebar.jsx` - Persistent Navigation
- Fixed left panel
- Icon + label navigation items
- Active state highlighting
- Aqua Security liquid glass styling

#### 3. `ContentPane.jsx` - Dynamic Content Area
- Scrollable main area
- Section-specific rendering
- Maintains scroll position per section

### Phase 2: Refactor Existing Pages

#### Transform Pages into Sections
- **DashboardPage** → `LiveDashboardSection`
- **SettingsPage tabs** → Individual sections
- **RecordingsPage** → `EventsHistorySection`
- **CameraManagementPage** → `CameraManagerSection`
- **FaceManagementPage** → `AIFacesSection`
- **AlertSettingsPage** → Part of `SystemSettingsSection`

### Phase 3: Implement Event Timeline

#### Collapsible Right Panel
- **Location**: Right side of content pane
- **Content**: Last 10-15 alerts
- **Features**:
  - Real-time updates via WebSocket
  - Click to jump to video clip
  - Filter by type (motion, face, unknown)
  - Timestamp display

---

## 📋 Detailed Section Specifications

### 1. Live Dashboard (Home) 🏠

**Layout**: Split into zones

```
┌────────────────────────────────────────────┬────────┐
│                                            │        │
│         Camera Grid/Cycle Display          │ Event  │
│         (Existing functionality)           │ Time-  │
│                                            │ line   │
│                                            │        │
├────────────────────────────────────────────┤ (Col-  │
│  Global Status Bar                         │ lapsi- │
│  "All systems nominal" or "⚠️ Alerts"     │  ble)  │
└────────────────────────────────────────────┴────────┘
```

**Components**:
- Camera grid with display mode controls
- Global status indicator
- Quick stats (people, recognitions today)
- Collapsible event timeline (right panel)

### 2. Events & History 🚨

**Layout**: Master-Detail pattern

```
┌────────────────────┬──────────────────────────┐
│  Date Range        │                          │
│  [Filter Buttons]  │                          │
│  ┌──────────────┐  │    Media Player          │
│  │ Event Card   │  │    (Video Playback)      │
│  │ [Thumbnail]  │  │                          │
│  │ Time/Date    │  │    [Download] [Delete]  │
│  │ Type         │  │                          │
│  └──────────────┘  │                          │
│  ┌──────────────┐  │                          │
│  │ Event Card   │  │                          │
│  └──────────────┘  │                          │
│  (Scrollable)      │                          │
└────────────────────┴──────────────────────────┘
```

**Features**:
- Timeline view of all events
- Filter by: Motion, Face Recognized, Unknown
- Date range picker
- Thumbnail previews
- Expandable video player

### 3. Camera Manager 📹

**Layout**: Master-Detail configuration

```
┌────────────────────┬──────────────────────────┐
│  Camera List       │  Selected Camera:        │
│  ┌──────────────┐  │  Front Door              │
│  │ ✓ Front Door │  │                          │
│  └──────────────┘  │  Tabs:                   │
│  ┌──────────────┐  │  [Connection] [Detection]│
│  │   Garage     │  │  [Schedule]              │
│  └──────────────┘  │                          │
│  ┌──────────────┐  │  Preview + Overlay Tools │
│  │   Backyard   │  │  (Motion zone drawing)   │
│  └──────────────┘  │                          │
│                    │                          │
│  [+ Discover]      │  [Save] [Test]          │
└────────────────────┴──────────────────────────┘
```

**Features**:
- List of all cameras (left)
- Active camera highlighted with cyan accent
- Configuration tabs (right)
- Live preview with motion zone overlay
- Camera discovery button

### 4. AI & Faces 👤

**Layout**: Gallery + Actions

```
┌─────────────────────────────────────────────┐
│  Known Faces Gallery                        │
│  ┌──────┐ ┌──────┐ ┌──────┐               │
│  │Image │ │Image │ │Image │               │
│  │Name  │ │Name  │ │Name  │               │
│  └──────┘ └──────┘ └──────┘               │
│                                             │
│  [➕ Enroll Face] (Cyan Primary Button)    │
│                                             │
│  AI Settings:                               │
│  ☑ Enable Facial Recognition               │
│  ☐ Enable Object Tracking                  │
│  Confidence Threshold: [━━━━━━○━] 0.6      │
│                                             │
│  Recent Recognitions:                       │
│  • John Doe - 2:34 PM                      │
│  • Unknown - 2:15 PM                       │
└─────────────────────────────────────────────┘
```

**Features**:
- Known faces grid (frosted glass cards)
- Prominent "Enroll Face" button
- AI configuration toggles
- Recent recognition log

### 5. System & Alerts ⚙️

**Layout**: List view (iOS/macOS Settings style)

```
┌─────────────────────────────────────────────┐
│  Alerts & Notifications                     │
│  ┌─────────────────────────────────────┐   │
│  │ Email Notifications          [✓]   │   │
│  │ Status: Connected                   │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ Telegram Bot                 [○]   │   │
│  │ Not configured                      │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Smart Home Integrations                    │
│  ┌─────────────────────────────────────┐   │
│  │ Home Assistant (MQTT)        [✓]   │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ HomeKit Bridge              [○]    │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  System Settings                            │
│  • Storage Paths                            │
│  • Display Modes                            │
│  • Recording Duration                       │
└─────────────────────────────────────────────┘
```

**Features**:
- Grouped settings by category
- Clear status indicators
- Expandable sections
- Success/failure states

---

## 🎨 Visual Design Principles

### Deference (Apple HIG)
- Content takes priority
- UI elements fade into background
- Camera feeds prominent
- Minimalist chrome

### Clarity
- High contrast text (white on charcoal)
- Clear iconography
- Consistent spacing
- Readable typography (Inter font)

### Depth
- Liquid glass layers
- Subtle shadows
- Backdrop blur effects
- Visual hierarchy through transparency

---

## 🔧 Technical Implementation

### Responsive Breakpoints

```css
/* Desktop (default) */
.sidebar { width: 220px; }
.content-pane { flex: 1; }

/* Tablet (iPad) */
@media (max-width: 1024px) {
  .sidebar { width: 180px; font-size: 0.9em; }
}

/* Mobile */
@media (max-width: 768px) {
  .sidebar { 
    position: fixed;
    width: 100%;
    height: 60px;
    bottom: 0;
    flex-direction: row;
  }
}
```

### State Management

```jsx
// App-level state for sidebar navigation
const [currentSection, setCurrentSection] = useState('live-dashboard');
const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

// Persist section in localStorage
useEffect(() => {
  localStorage.setItem('openeye-section', currentSection);
}, [currentSection]);
```

### Routing Strategy

**Option 1**: Keep React Router (Recommended)
```jsx
<Route path="/" element={<MainLayout />}>
  <Route index element={<Navigate to="/live" />} />
  <Route path="live" element={<LiveDashboardSection />} />
  <Route path="events" element={<EventsHistorySection />} />
  <Route path="cameras" element={<CameraManagerSection />} />
  <Route path="ai-faces" element={<AIFacesSection />} />
  <Route path="system" element={<SystemSettingsSection />} />
  <Route path="themes" element={<ThemeSelectorSection />} />
</Route>
```

**Option 2**: Single-page with conditional rendering
```jsx
<MainLayout currentSection={section}>
  {section === 'live' && <LiveDashboardSection />}
  {section === 'events' && <EventsHistorySection />}
  {/* etc */}
</MainLayout>
```

---

## 📦 File Structure

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── MainLayout.jsx         # Master container
│   │   ├── Sidebar.jsx            # Persistent navigation
│   │   ├── ContentPane.jsx        # Main content area
│   │   ├── TopBar.jsx             # Global status bar
│   │   └── EventTimeline.jsx      # Collapsible right panel
│   └── ...
├── sections/
│   ├── LiveDashboardSection.jsx   # 🏠 Main monitoring view
│   ├── EventsHistorySection.jsx   # 🚨 Recordings & playback
│   ├── CameraManagerSection.jsx   # 📹 Camera configuration
│   ├── AIFacesSection.jsx         # 👤 Face recognition
│   ├── SystemSettingsSection.jsx  # ⚙️ Global settings
│   └── ThemeSelectorSection.jsx   # 🎨 Theme picker
└── ...
```

---

## ⚡ Performance Considerations

### Lazy Loading
```jsx
const EventsHistorySection = lazy(() => import('./sections/EventsHistorySection'));
```

### Memoization
```jsx
const Sidebar = memo(({ currentSection, onNavigate }) => { ... });
```

### Virtual Scrolling
- Use `react-window` for large event lists
- Infinite scroll for timeline

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create `MainLayout`, `Sidebar`, `ContentPane` components
- [ ] Implement basic routing
- [ ] Apply Aqua Security liquid glass styles
- [ ] Test responsive behavior

### Phase 2: Content Migration (Week 2)
- [ ] Convert Dashboard → LiveDashboardSection
- [ ] Implement EventTimeline component
- [ ] Migrate Camera/Face/Alert pages to sections
- [ ] Test navigation flow

### Phase 3: Polish & Optimization (Week 3)
- [ ] Add transitions and animations
- [ ] Implement keyboard shortcuts
- [ ] Optimize performance
- [ ] User testing and feedback

### Phase 4: Documentation (Week 4)
- [ ] Update user guide
- [ ] Create developer docs
- [ ] Record demo video
- [ ] Update README

---

## 📊 Success Metrics

### User Experience
- [ ] Reduced clicks to access features
- [ ] Faster navigation (< 200ms transitions)
- [ ] Improved workflow efficiency
- [ ] Positive user feedback

### Technical
- [ ] No performance regression
- [ ] Mobile responsive
- [ ] Accessibility compliant (WCAG 2.1 AA)
- [ ] Cross-browser compatibility

---

## 🎯 Future Enhancements

### V1 (This Release)
- Basic HIG Split View layout
- Persistent sidebar navigation
- Event timeline (right panel)

### V2 (Future)
- Customizable sidebar (reorder items)
- Collapsible sidebar (more screen space)
- Keyboard shortcuts
- Search functionality

### V3 (Future)
- Multi-window support
- Drag-and-drop camera arrangement
- Picture-in-picture mode
- Custom layouts (user-defined)

---

## 📝 Notes for Implementation

### Compatibility
- Ensure existing functionality remains intact
- Support both Docker and native installations
- Maintain theme system compatibility
- Preserve user settings

### Testing
- Test on Desktop (Chrome, Firefox, Safari, Edge)
- Test on Tablet (iPad, Android tablet)
- Test on Mobile (iOS, Android)
- Test keyboard navigation
- Test with screen readers

### Rollout Strategy
- Feature flag for gradual rollout
- Beta testing with select users
- Fallback to classic layout option
- Monitor performance metrics

---

*Document prepared by: GitHub Copilot*  
*Project: OpenEye Surveillance System*  
*Target Version: 3.5.2*  
*Status: Planning Phase - Ready for Implementation*
