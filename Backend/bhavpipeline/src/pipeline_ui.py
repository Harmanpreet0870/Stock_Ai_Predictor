# ====================================================
# File Role    : Support File
# File Name    : pipeline_ui.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Console UI display for pipeline status reports
# ====================================================

import os

TABLE_WIDTH     = 80
SEPARATOR_CHAR  = "═"
THIN_SEPARATOR  = "─"

FLAG_DESCRIPTIONS = {
    -2: "Error - requires review/retry",
    -1: "Holiday - no processing",
     0: "Pending - eligible for execution",
     1: "Done - completed successfully",
     2: "Rolled out - archived",
}


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def display_header():
    print()
    print("  ╔" + SEPARATOR_CHAR * (TABLE_WIDTH - 4) + "╗")
    print("  ║" + "PIPELINE MONITORING STATUS REPORT".center(TABLE_WIDTH - 4) + "║")
    print("  ╚" + SEPARATOR_CHAR * (TABLE_WIDTH - 4) + "╝")
    print()


def display_component_table(component_status):
    print("  ┌" + THIN_SEPARATOR * (TABLE_WIDTH - 4) + "┐")
    print("  │" + " COMPONENT STATUS ".center(TABLE_WIDTH - 4) + "│")
    print("  ├" + THIN_SEPARATOR * 18 + "┬" + THIN_SEPARATOR * 30 + "┬" + THIN_SEPARATOR * 10 + "┬" + THIN_SEPARATOR * 16 + "┤")
    print("  │" + " Component ID".ljust(17) + "│" + " Name".ljust(29) + "│" + " Enabled".ljust(9) + "│" + " Status".ljust(15) + "│")
    print("  ├" + THIN_SEPARATOR * 18 + "┼" + THIN_SEPARATOR * 30 + "┼" + THIN_SEPARATOR * 10 + "┼" + THIN_SEPARATOR * 16 + "┤")
    if component_status is None:
        print("  │" + " [Data unavailable]".ljust(TABLE_WIDTH - 6) + "│")
    else:
        for comp in component_status.get('components', []):
            comp_id = str(comp.get('component_id', 'N/A'))[:16]
            name    = str(comp.get('name', 'N/A'))[:28]
            enabled = "Yes" if comp.get('enabled', False) else "No"
            status  = comp.get('status', 'Unknown')[:14]
            print(f"  │ {comp_id.ljust(16)}│ {name.ljust(28)}│ {enabled.ljust(8)}│ {status.ljust(14)}│")
    print("  └" + THIN_SEPARATOR * 18 + "┴" + THIN_SEPARATOR * 30 + "┴" + THIN_SEPARATOR * 10 + "┴" + THIN_SEPARATOR * 16 + "┘")
    if component_status and 'summary' in component_status:
        s = component_status['summary']
        print(f"  Summary: Active: {s.get('active', 0)} | Inactive: {s.get('inactive', 0)} | Total: {s.get('total', 0)}")
    print()


def display_file_table(file_status):
    print("  ┌" + THIN_SEPARATOR * (TABLE_WIDTH - 4) + "┐")
    print("  │" + " FILE AVAILABILITY ".center(TABLE_WIDTH - 4) + "│")
    print("  ├" + THIN_SEPARATOR * 18 + "┬" + THIN_SEPARATOR * 48 + "┬" + THIN_SEPARATOR * 8 + "┤")
    print("  │" + " Component ID".ljust(17) + "│" + " File Path".ljust(47) + "│" + " Exists".ljust(7) + "│")
    print("  ├" + THIN_SEPARATOR * 18 + "┼" + THIN_SEPARATOR * 48 + "┼" + THIN_SEPARATOR * 8 + "┤")
    if file_status is None:
        print("  │" + " [Data unavailable]".ljust(TABLE_WIDTH - 6) + "│")
    else:
        for fi in file_status.get('files', []):
            comp_id   = str(fi.get('component_id', 'N/A'))[:16]
            file_path = str(fi.get('file_path', 'N/A'))
            if len(file_path) > 46:
                file_path = "..." + file_path[-43:]
            exists = "Yes" if fi.get('exists', False) else "No"
            print(f"  │ {comp_id.ljust(16)}│ {file_path[:46].ljust(46)}│ {exists.ljust(6)}│")
    print("  └" + THIN_SEPARATOR * 18 + "┴" + THIN_SEPARATOR * 48 + "┴" + THIN_SEPARATOR * 8 + "┘")
    if file_status and 'summary' in file_status:
        s = file_status['summary']
        print(f"  Summary: Found: {s.get('found', 0)} | Missing: {s.get('missing', 0)} | Total: {s.get('total', 0)}")
    print()


def display_flag_status(date_info, flag_status):
    print("  ┌" + THIN_SEPARATOR * (TABLE_WIDTH - 4) + "┐")
    print("  │" + " PREVIOUS WORKING DAY FLAG STATUS ".center(TABLE_WIDTH - 4) + "│")
    print("  ├" + THIN_SEPARATOR * 28 + "┬" + THIN_SEPARATOR * 45 + "┤")
    print("  │" + " Field".ljust(27) + "│" + " Value".ljust(44) + "│")
    print("  ├" + THIN_SEPARATOR * 28 + "┼" + THIN_SEPARATOR * 45 + "┤")
    if date_info:
        for label, key in [("Max WID", "max_wid"), ("Previous WID", "previous_wid"),
                            ("Date (gdate)", "gdate"), ("Trading Date (tsdate)", "tsdate")]:
            print(f"  │ {label.ljust(26)}│ {str(date_info.get(key, 'N/A')).ljust(43)}│")
        is_working = "Yes" if date_info.get('is_working_day', False) else "No"
        hf = date_info.get('isholidayflag', 'N/A')
        print(f"  │ {'Is Working Day'.ljust(26)}│ {f'{is_working} (isholidayflag={hf})'.ljust(43)}│")
    if flag_status:
        bpf = flag_status.get('bhavpip_flag', 'N/A')
        desc = FLAG_DESCRIPTIONS.get(bpf, 'Unknown')
        print(f"  │ {'bhavpip_flag Value'.ljust(26)}│ {f'{bpf} ({desc})'.ljust(43)}│")
        print(f"  │ {'Status'.ljust(26)}│ {str(flag_status.get('status', 'N/A')).ljust(43)}│")
    print("  └" + THIN_SEPARATOR * 28 + "┴" + THIN_SEPARATOR * 45 + "┘")
    print()


def display_errors(errors):
    if not errors:
        return
    print("  ╔" + SEPARATOR_CHAR * (TABLE_WIDTH - 4) + "╗")
    print("  ║" + " ERRORS ENCOUNTERED ".center(TABLE_WIDTH - 4) + "║")
    print("  ╠" + SEPARATOR_CHAR * (TABLE_WIDTH - 4) + "╣")
    for idx, error in enumerate(errors):
        module = error.get('module', 'Unknown')
        msg    = error.get('error', 'Unknown error')
        print(f"  ║  Module: {module.ljust(TABLE_WIDTH - 15)}║")
        for line in [msg[i:i+TABLE_WIDTH-15] for i in range(0, len(msg), TABLE_WIDTH-15)]:
            print(f"  ║  Error:  {line.ljust(TABLE_WIDTH - 15)}║")
        if idx < len(errors) - 1:
            print("  ╟" + THIN_SEPARATOR * (TABLE_WIDTH - 4) + "╢")
    print("  ╚" + SEPARATOR_CHAR * (TABLE_WIDTH - 4) + "╝")
    print()


def determine_blocking_conditions(results):
    blocking_reasons = []
    warning_only     = []
    if results.get('errors'):
        for e in results['errors']:
            warning_only.append(f"Error in {e.get('module', 'Unknown')}: {e.get('error', '')[:50]}")
    file_status = results.get('file_status')
    if file_status:
        missing_enabled = file_status.get('summary', {}).get('missing_enabled', 0)
        if missing_enabled > 0:
            blocking_reasons.append(f"Missing {missing_enabled} enabled component file(s)")
    flag_status = results.get('flag_status')
    if flag_status and not flag_status.get('can_proceed', False):
        blocking_reasons.append(f"bhavpip_flag: {flag_status.get('status')} — {flag_status.get('message', '')[:50]}")
    exec_validation = results.get('execution_validation')
    if exec_validation and not exec_validation.get('allowed', True):
        blocking_reasons.append(f"Execution blocked: {exec_validation.get('reason', '')[:60]}")
    return {
        'blocking_reasons': blocking_reasons,
        'warning_only': warning_only,
        'has_blocking': bool(blocking_reasons),
        'has_warnings': bool(warning_only),
    }


def display_and_confirm(results):
    clear_screen()
    display_header()
    display_component_table(results.get('component_status'))
    display_file_table(results.get('file_status'))
    display_flag_status(results.get('date_info'), results.get('flag_status'))
    display_errors(results.get('errors', []))
    conditions = determine_blocking_conditions(results)

    if conditions['has_blocking']:
        print("  ⛔ Blocking conditions exist.")
        for r in conditions['blocking_reasons']:
            print(f"    • {r}")
        print()
    if conditions['has_warnings']:
        for w in conditions['warning_only']:
            print(f"  ⚠  {w}")
        print()

    if conditions['has_blocking']:
        prompt = "  Blocking conditions exist. Proceed anyway? (yes/no): "
    else:
        print("  ✅ All critical checks passed.")
        prompt = "  Proceed with pipeline execution? (yes/no): "

    while True:
        user_input = input(prompt).strip().lower()
        if user_input in ('yes', 'y'):
            return True
        elif user_input in ('no', 'n'):
            return False
        print("  Enter 'yes' or 'no'.")
