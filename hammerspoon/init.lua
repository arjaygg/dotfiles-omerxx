-- Hammerspoon config
-- Enable IPC (required for `hs` CLI)
require("hs.ipc")

--------------------------------------------------------------------------------
-- DAMAGED MONITOR GUARD
-- Monitor "X315 MAX" has damage on the left ~480px.
-- Any window that lands on that monitor gets pushed into the safe zone.
--------------------------------------------------------------------------------

local DAMAGED_SCREEN_NAME = "X315 MAX"
local DEAD_ZONE_WIDTH = 420  -- pixels from left edge of the monitor to avoid (damaged strip)

-- Returns the safe frame for the damaged monitor (usable area only)
local function safeFrame(screen)
  local f = screen:frame()
  return hs.geometry.rect(f.x + DEAD_ZONE_WIDTH, f.y, f.w - DEAD_ZONE_WIDTH, f.h)
end

-- Clamp a window into the safe zone if it's on the damaged monitor
local function enforceDeadZone(win)
  if not win or not win:isStandard() then return end

  local screen = win:screen()
  if not screen or screen:name() ~= DAMAGED_SCREEN_NAME then return end

  local wf = win:frame()
  local safe = safeFrame(screen)

  local changed = false

  -- If window's left edge is inside the dead zone, push it right
  if wf.x < safe.x then
    wf.x = safe.x
    changed = true
  end

  -- If window is wider than the safe zone, shrink it to fit
  if wf.x + wf.w > safe.x + safe.w then
    wf.w = safe.x + safe.w - wf.x
    changed = true
  end

  if changed then
    win:setFrame(wf)
  end
end

-- Watch for window creation and movement
local wf = hs.window.filter.new()
wf:subscribe({
  hs.window.filter.windowCreated,
  hs.window.filter.windowMoved,
  hs.window.filter.windowOnScreen,
}, function(win)
  enforceDeadZone(win)
end)

-- Also enforce on all existing windows right now
hs.timer.doAfter(1, function()
  for _, win in ipairs(hs.window.allWindows()) do
    enforceDeadZone(win)
  end
end)

hs.alert.show("Dead-zone guard active for " .. DAMAGED_SCREEN_NAME)

--------------------------------------------------------------------------------
-- HELP — Ctrl+Alt+/ shows all custom hotkeys
--------------------------------------------------------------------------------

hs.hotkey.bind({"ctrl", "alt"}, "/", function()
  hs.alert.show(
    "Hammerspoon Hotkeys\n" ..
    "-------------------\n" ..
    "Ctrl+Alt+T  Move Teams to primary screen\n" ..
    "Ctrl+Alt+C  Toggle Cisco auto-hide\n" ..
    "Ctrl+Alt+/  Show this help",
    4
  )
end)

--------------------------------------------------------------------------------
-- TEAMS → PRIMARY SCREEN GUARD
-- Keep Microsoft Teams on the built-in display unless manually moved.
-- "Manually moved" = user drags it to another screen. Once moved, we stop
-- enforcing until the window is closed/recreated or Hammerspoon reloads.
--------------------------------------------------------------------------------

local PRIMARY_SCREEN_NAME = "Built-in Retina Display"

-- hs.screen.find uses pattern matching where "-" is special; use helper instead
local function findScreenByName(name)
  for _, s in ipairs(hs.screen.allScreens()) do
    if s:name() == name then return s end
  end
  return nil
end
local TEAMS_BUNDLE_IDS = {
  ["com.microsoft.teams2"] = true,
  ["com.microsoft.teams2.notificationcenter"] = true,
}

-- Track windows the user has manually moved (by window ID)
local teamsManuallyMoved = {}

-- Moves a Teams window to the primary screen, preserving its size
local function moveTeamsToPrimary(win)
  if not win or not win:isStandard() then return end
  local app = win:application()
  if not app or not TEAMS_BUNDLE_IDS[app:bundleID()] then return end

  local screen = win:screen()
  if not screen then return end

  -- Already on primary screen — nothing to do
  if screen:name() == PRIMARY_SCREEN_NAME then
    teamsManuallyMoved[win:id()] = nil
    return
  end

  -- If user manually moved it, respect that
  if teamsManuallyMoved[win:id()] then return end

  -- Move to primary screen
  local primary = findScreenByName(PRIMARY_SCREEN_NAME)
  if not primary then return end
  win:moveToScreen(primary, true)
end

-- Watch Teams windows
local teamsFilter = hs.window.filter.new(function(win)
  local app = win:application()
  return app and TEAMS_BUNDLE_IDS[app:bundleID()] or false
end)

-- On creation: move to primary
teamsFilter:subscribe(hs.window.filter.windowCreated, function(win)
  moveTeamsToPrimary(win)
end)

-- On move: detect if user moved it away from primary (manual override)
-- Hotkey: Ctrl+Alt+T — find Teams and move it to the primary screen
hs.hotkey.bind({"ctrl", "alt"}, "T", function()
  local primary = findScreenByName(PRIMARY_SCREEN_NAME)
  if not primary then
    hs.alert.show("Primary screen not found")
    return
  end
  local moved = false
  for _, win in ipairs(hs.window.allWindows()) do
    local app = win:application()
    if app and TEAMS_BUNDLE_IDS[app:bundleID()] and win:isStandard() then
      teamsManuallyMoved[win:id()] = nil
      win:moveToScreen(primary, true)
      win:focus()
      moved = true
    end
  end
  if not moved then
    hs.alert.show("No Teams window found")
  end
end)

teamsFilter:subscribe(hs.window.filter.windowMoved, function(win)
  if not win or not win:isStandard() then return end
  local screen = win:screen()
  if screen and screen:name() ~= PRIMARY_SCREEN_NAME then
    teamsManuallyMoved[win:id()] = true
  else
    teamsManuallyMoved[win:id()] = nil
  end
end)

--------------------------------------------------------------------------------
-- CISCO SECURE CLIENT — AUTO-HIDE
-- The "Cisco Secure Client | Secure VPN" window randomly pops up.
-- Auto-hide it whenever it appears. Only targets this exact window.
--------------------------------------------------------------------------------

local CISCO_BUNDLE_ID = "com.cisco.secureclient.gui"
local CISCO_TITLE = "Cisco Secure Client | Secure VPN"
local ciscoAutoHide = true  -- on by default

-- Ctrl+Alt+C — toggle Cisco auto-hide
hs.hotkey.bind({"ctrl", "alt"}, "C", function()
  ciscoAutoHide = not ciscoAutoHide
  if ciscoAutoHide then
    hs.alert.show("Cisco auto-hide: ON")
  else
    hs.alert.show("Cisco auto-hide: OFF")
  end
end)

local ciscoFilter = hs.window.filter.new(function(win)
  local app = win:application()
  return app and app:bundleID() == CISCO_BUNDLE_ID
end)

ciscoFilter:subscribe({
  hs.window.filter.windowCreated,
  hs.window.filter.windowOnScreen,
}, function(win)
  if not ciscoAutoHide then return end
  if not win then return end
  if win:title() == CISCO_TITLE then
    local app = win:application()
    if app then app:hide() end
  end
end)
