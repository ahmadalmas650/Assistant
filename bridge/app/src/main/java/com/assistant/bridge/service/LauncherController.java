package com.assistant.bridge.service;

import android.accessibilityservice.AccessibilityService;
import android.content.Context;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.Locale;

/**
 * LauncherController launches apps the way a human does: go to the home
 * screen, open the launcher's search box, type the app name, verify the
 * name in the resulting text, click the icon, and confirm the launch by
 * checking the foreground package. Package names are never used to
 * launch, so apps whose names differ from their package identifiers
 * work correctly, and an app that is not installed produces an honest
 * "not found" answer because it never appears in the search results.
 */
final class LauncherController {

    private static final String TAG = "JARVIS_Launcher";

    private LauncherController() {
    }

    /**
     * Launch an app by its visible name through the launcher search UI.
     * Returns a JSON result string; never throws.
     */
    static String launchByName(Context context, AccessibilityBridgeService svc, String appName) {
        if (svc == null) {
            return "{\"ok\":false,\"error\":\"accessibility service not connected\"}";
        }
        if (appName == null || appName.trim().isEmpty()) {
            return "{\"ok\":false,\"error\":\"no app name given\"}";
        }
        String name = appName.trim();

        // Step 1: go to the home screen.
        svc.pressHome();
        sleep(900);

        String launcher = svc.getLauncherPackage();
        if (launcher == null || launcher.isEmpty()) {
            return "{\"ok\":false,\"error\":\"default launcher not found\"}";
        }

        // Step 2: find the launcher's search box (editable node).
        AccessibilityNodeInfo searchBox = null;
        for (int attempt = 0; attempt < 8 && searchBox == null; attempt++) {
            searchBox = findEditableNode(svc.getCurrentRootNode());
            if (searchBox == null) {
                // Many launchers reveal the search box only after swiping
                // up or tapping it; try a small upward swipe once.
                if (attempt == 3) {
                    svc.swipe(540, 1200, 540, 400, 200);
                }
                sleep(500);
            }
        }
        if (searchBox == null) {
            return "{\"ok\":false,\"error\":\"launcher search box not found on home screen\"}";
        }

        // Step 3: type the app name into the search box.
        boolean typed = svc.setText(searchBox, name);
        searchBox.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        if (!typed) {
            searchBox.recycle();
            return "{\"ok\":false,\"error\":\"could not type into launcher search box\"}";
        }
        searchBox.recycle();
        sleep(1200);

        // Step 4: verify the name in the search results and click the icon.
        AccessibilityNodeInfo icon = null;
        for (int attempt = 0; attempt < 8 && icon == null; attempt++) {
            AccessibilityNodeInfo root = svc.getCurrentRootNode();
            if (root != null) {
                icon = findNodeMatching(root, name);
                root.recycle();
            }
            if (icon == null) {
                sleep(500);
            }
        }
        if (icon == null) {
            // Not in the results: the app is not installed (or the launcher
            // cannot surface it). Clear the search and report honestly.
            svc.pressBack();
            sleep(300);
            svc.pressBack();
            return "{\"ok\":false,\"error\":\"app not found on this device: " + name + "\"}";
        }
        boolean clicked = svc.performClick(icon);
        icon.recycle();
        if (!clicked) {
            svc.pressBack();
            return "{\"ok\":false,\"error\":\"could not click app icon: " + name + "\"}";
        }

        // Step 5: confirm the launch by checking the foreground package.
        String launchedPackage = "";
        for (int attempt = 0; attempt < 10; attempt++) {
            sleep(600);
            String pkg = svc.getCurrentPackageName();
            if (pkg != null && !pkg.isEmpty() && !launcher.equals(pkg)) {
                launchedPackage = pkg;
                break;
            }
        }
        if (launchedPackage.isEmpty()) {
            return "{\"ok\":false,\"error\":\"clicked icon but app did not open: " + name + "\"}";
        }
        return "{\"ok\":true,\"method\":\"accessibility_search\",\"app\":" + json(name)
                + ",\"package\":" + json(launchedPackage) + "}";
    }

    /**
     * Launch by package identifier. Intentionally NOT implemented: every
     * launch must go through the human-style launcher search above, so
     * package-based launching does not exist anywhere in this bridge.
     */

    static String isInstalled(Context context, String pkg) {
        if (pkg == null || pkg.trim().isEmpty()) {
            return "{\"ok\":false,\"error\":\"no package given\"}";
        }
        try {
            context.getPackageManager().getPackageInfo(pkg.trim(), 0);
            return "{\"ok\":true,\"installed\":true,\"package\":" + json(pkg.trim()) + "}";
        } catch (Exception e) {
            return "{\"ok\":true,\"installed\":false,\"package\":" + json(pkg.trim()) + "}";
        }
    }

    // ------------------------------------------------------------------
    // Node search helpers
    // ------------------------------------------------------------------

    /**
     * Find a node whose visible text or content description matches the
     * query (case-insensitive contains). Prefer clickable nodes.
     */
    private static AccessibilityNodeInfo findNodeMatching(AccessibilityNodeInfo root, String query) {
        if (root == null || query == null) {
            return null;
        }
        String q = query.toLowerCase(Locale.ROOT);
        AccessibilityNodeInfo best = null;
        AccessibilityNodeInfo any = null;
        for (int i = 0; i < root.getChildCount(); i++) {
            AccessibilityNodeInfo child = root.getChild(i);
            if (child == null) {
                continue;
            }
            String text = charSeqToString(child.getText());
            String desc = charSeqToString(child.getContentDescription());
            // Skip editable nodes: after typing, the search box itself
            // matches the query but clicking it would not launch anything.
            boolean textMatch = text != null && !child.isEditable()
                    && text.toLowerCase(Locale.ROOT).contains(q);
            boolean descMatch = desc != null
                    && desc.toLowerCase(Locale.ROOT).contains(q);
            if (textMatch || descMatch) {
                if (child.isClickable()) {
                    if (best != null) {
                        best.recycle();
                    }
                    best = child;
                    continue;
                }
                if (any == null) {
                    any = child;
                    continue;
                }
                child.recycle();
                continue;
            }
            AccessibilityNodeInfo deeper = findNodeMatching(child, query);
            child.recycle();
            if (deeper != null) {
                if (deeper.isClickable()) {
                    if (best != null) {
                        best.recycle();
                    }
                    best = deeper;
                } else if (any == null) {
                    any = deeper;
                } else {
                    deeper.recycle();
                }
            }
        }
        if (best != null) {
            if (any != null) {
                any.recycle();
            }
            return best;
        }
        return any;
    }

    private static AccessibilityNodeInfo findEditableNode(AccessibilityNodeInfo root) {
        if (root == null) {
            return null;
        }
        if (root.isEditable()) {
            return root;
        }
        for (int i = 0; i < root.getChildCount(); i++) {
            AccessibilityNodeInfo child = root.getChild(i);
            if (child == null) {
                continue;
            }
            AccessibilityNodeInfo found = findEditableNode(child);
            if (found != null) {
                if (found != child) {
                    child.recycle();
                }
                return found;
            }
            child.recycle();
        }
        return null;
    }

    private static String charSeqToString(CharSequence cs) {
        if (cs == null || cs.length() == 0) {
            return null;
        }
        String s = cs.toString().trim();
        return s.isEmpty() ? null : s;
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static String json(String s) {
        if (s == null) {
            return "\"\"";
        }
        StringBuilder sb = new StringBuilder(s.length() + 8);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n");  break;
                case '\r': sb.append("\\r");  break;
                case '\t': sb.append("\\t");  break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }
}
