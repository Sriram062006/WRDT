/**
 * English / Tamil strings.
 *
 * WRDT supervisors in Krishnagiri work in Tamil, so the register labels
 * in particular need both. Keys are grouped by screen; anything missing
 * from `ta` falls back to `en` via the Proxy in `useT`, so a half-
 * translated key shows English rather than `undefined`.
 */
export const STRINGS = {
  en: {
    appName: "WRDT",
    tagline: "Women And Rural Development Trust",
    taTagline: "\u0baa\u0bc6\u0ba3\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bb3\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf - \u0ba8\u0bae\u0bcd\u0bae\u0ba4\u0bc1 \u0bae\u0bc1\u0ba9\u0bcd\u0ba9\u0bc7\u0bb1\u0bcd\u0bb1\u0bae\u0bcd",
    loginTitle: "Login to your account",
    loginSub: "Welcome back! Please login to continue.",
    email: "Email", password: "Password", loginBtn: "Login", signingIn: "Signing in...",
    langLabel: "Language / \u0bae\u0bca\u0bb4\u0bbf", logout: "Log out",
    forgotPwd: "Forgot password?",
    forgotHelp:
      "WRDT accounts are issued by your organization's Owner. Ask them to reset your password from Settings \u2192 Users.",

    dashboard: "Dashboard", regions: "Regions", groups: "Groups", members: "Members",
    meetings: "Meetings", loans: "Loans", reports: "Reports", expenses: "Expenses",
    activity: "Activity", settings: "Settings", excelImport: "Excel Import",

    todayCol: "Today's Collection", totRegions: "Total Regions", totGroups: "Total Groups",
    totMembers: "Total Members", openMeetings: "Open Meetings",
    outLoans: "Outstanding Loans", totalSavingsHeld: "Total Savings Held",
    completedThisMonth: "Completed This Month",
    collChart: "Collections (last 60 days)", noChartData: "No collections recorded yet.",
    goodMorn: "Good Morning", goodAftn: "Good Afternoon", goodEvng: "Good Evening",

    search: "Search...", showing: "Showing", of: "of", entries: "entries",
    status: "Status", action: "Actions", name: "Name", save: "Save", cancel: "Cancel",
    del: "Delete", edit: "Edit", add: "Add", close: "Close", retry: "Retry",
    loading: "Loading...", noData: "Nothing here yet.", prev: "Previous", next: "Next",

    regionName: "Region Name", groupName: "Group Name", memberName: "Member Name",
    formedDate: "Formed", joinedDate: "Joined", phone: "Phone", memberCode: "Member ID",
    addRegion: "Add Region", addGroup: "Add Group", addMember: "Add Member",
    region: "Region", group: "Group", prevSavings: "Previous Savings",

    meeting: "Meeting", date: "Date", startMeeting: "Start Meeting",
    viewMeetings: "Meetings", openRegister: "Open", viewRegister: "View",
    completed: "Completed", inProgress: "In Progress",
    complete: "Complete Meeting", saveSheet: "Save Register",
    prevSaving: "Prev Saving", thisWeek: "This Meeting", totalSaving: "Total Saving",
    loanGiven: "Loan Given", paidTillDate: "Paid Till Date", principalPaid: "Principal Paid",
    interest: "Interest", remainingLoan: "Remaining Loan", fine: "Fine",
    cashPaid: "Cash Paid", remarks: "Remarks", present: "Present",
    applyAll: "Apply the same saving to everyone", savingAmt: "Amount", apply: "Apply",
    membersPresent: "Members Present", membersAbsent: "Members Absent",
    todayExpenses: "Meeting Expenses", mtgSummary: "Meeting Summary",
    savingsCollection: "Savings Collected", loansGiven: "Loans Given",
    installColl: "Principal Collected", finesColl: "Fines Collected",
    interestColl: "Interest Collected", totalExpense: "Total Expense",
    cashInHand: "Cash in Hand", expenseType: "Expense Type", amount: "Amount",
    addExpense: "Add Expense", exportXls: "Export Excel", printReg: "Print",
    lockWarning:
      "Completing locks this meeting permanently. Nothing in it can be changed afterwards, and its closing balances become next meeting's opening balances.",
    lockedNotice: "This meeting is completed and permanently locked.",
    unsaved: "Unsaved changes", saved: "All changes saved", saving: "Saving...",

    loanLedger: "Outstanding Loans", totalOutstanding: "Total Outstanding",
    asOf: "As of", noLoans: "No outstanding loans.",
    expenseSummary: "By Type", allExpenses: "All Expenses", total: "Total",
    monthlyReport: "Monthly Report", groupReport: "Group Report", month: "Month", year: "Year",
    users: "Users", addUser: "Add User", role: "Role", assignedGroups: "Assigned Groups",
    changePassword: "Change Password", currentPassword: "Current Password",
    newPassword: "New Password", confirmPassword: "Confirm New Password",
    deactivate: "Deactivate", active: "Active", inactive: "Inactive",
    myAccount: "My Account", owner: "Owner", supervisor: "Supervisor",
    uploadFile: "Choose Excel File", downloadTemplate: "Download Template",
    importNow: "Import Now", importAnother: "Import Another File",
    importComplete: "Import Complete", rowsTotal: "Total Rows",
    newRegions: "New Regions", newGroups: "New Groups", newMembers: "New Members",
    duplicatesSkipped: "Duplicates Skipped", invalidRows: "Invalid Rows",
  },
  ta: {
    loginTitle: "\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0ba8\u0bc1\u0bb4\u0bc8\u0baf\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
    loginSub: "\u0bb5\u0bb0\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbf\u0bb1\u0bcb\u0bae\u0bcd! \u0ba4\u0bca\u0b9f\u0bb0 \u0b89\u0bb3\u0bcd\u0ba8\u0bc1\u0bb4\u0bc8\u0baf\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
    email: "\u0bae\u0bbf\u0ba9\u0bcd\u0ba9\u0b9e\u0bcd\u0b9a\u0bb2\u0bcd", password: "\u0b95\u0b9f\u0bb5\u0bc1\u0b9a\u0bcd\u0b9a\u0bca\u0bb2\u0bcd",
    loginBtn: "\u0b89\u0bb3\u0bcd\u0ba8\u0bc1\u0bb4\u0bc8", logout: "\u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bc1",
    dashboard: "\u0b9f\u0bbe\u0bb7\u0bcd\u0baa\u0bcb\u0bb0\u0bcd\u0b9f\u0bc1", regions: "\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0b95\u0bb3\u0bcd",
    groups: "\u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd", members: "\u0b89\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
    meetings: "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd", loans: "\u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd",
    reports: "\u0b85\u0bb1\u0bbf\u0b95\u0bcd\u0b95\u0bc8\u0b95\u0bb3\u0bcd", expenses: "\u0b9a\u0bc6\u0bb2\u0bb5\u0bc1\u0b95\u0bb3\u0bcd",
    activity: "\u0b9a\u0bc6\u0baf\u0bb2\u0bcd\u0baa\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bcd", settings: "\u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd",
    excelImport: "\u0b8e\u0b95\u0bcd\u0bb8\u0bc6\u0bb2\u0bcd \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0ba4\u0bbf",
    todayCol: "\u0b87\u0ba9\u0bcd\u0bb1\u0bc8\u0baf \u0bb5\u0b9a\u0bc2\u0bb2\u0bcd",
    totRegions: "\u0bae\u0bca\u0ba4\u0bcd\u0ba4 \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0b95\u0bb3\u0bcd",
    totGroups: "\u0bae\u0bca\u0ba4\u0bcd\u0ba4 \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd",
    totMembers: "\u0bae\u0bca\u0ba4\u0bcd\u0ba4 \u0b89\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
    outLoans: "\u0ba8\u0bbf\u0bb2\u0bc1\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd",
    goodMorn: "\u0b95\u0bbe\u0bb2\u0bc8 \u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd",
    goodAftn: "\u0bae\u0ba4\u0bbf\u0baf \u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd",
    goodEvng: "\u0bae\u0bbe\u0bb2\u0bc8 \u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd",
    search: "\u0ba4\u0bc7\u0b9f\u0bc1\u0b95...", save: "\u0b9a\u0bc7\u0bae\u0bbf", cancel: "\u0bb0\u0ba4\u0bcd\u0ba4\u0bc1",
    del: "\u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bc1", edit: "\u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1",
    loading: "\u0b8f\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1...",
    regionName: "\u0baa\u0b95\u0bc1\u0ba4\u0bbf \u0baa\u0bc6\u0baf\u0bb0\u0bcd",
    groupName: "\u0b95\u0bc1\u0bb4\u0bc1 \u0baa\u0bc6\u0baf\u0bb0\u0bcd",
    memberName: "\u0b89\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bb0\u0bcd \u0baa\u0bc6\u0baf\u0bb0\u0bcd",
    meeting: "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bae\u0bcd", date: "\u0ba4\u0bc7\u0ba4\u0bbf",
    startMeeting: "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0ba4\u0bca\u0b9f\u0b99\u0bcd\u0b95\u0bc1",
    completed: "\u0bae\u0bc1\u0b9f\u0bbf\u0ba8\u0bcd\u0ba4\u0ba4\u0bc1",
    inProgress: "\u0ba8\u0b9f\u0bc8\u0baa\u0bc6\u0bb1\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1",
    complete: "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bc8 \u0bae\u0bc1\u0b9f\u0bbf",
    prevSaving: "\u0bae\u0bc1\u0ba8\u0bcd\u0ba4\u0bc8\u0baf \u0b9a\u0bc7\u0bae\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
    thisWeek: "\u0b87\u0ba8\u0bcd\u0ba4 \u0bb5\u0bbe\u0bb0 \u0b9a\u0bc7\u0bae\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
    totalSaving: "\u0bae\u0bca\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc7\u0bae\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
    loanGiven: "\u0b95\u0b9f\u0ba9\u0bcd", principalPaid: "\u0ba4\u0bb5\u0ba3\u0bc8",
    interest: "\u0bb5\u0b9f\u0bcd\u0b9f\u0bbf", fine: "\u0b85\u0baa\u0bb0\u0bbe\u0ba4\u0bae\u0bcd",
    cashPaid: "\u0baa\u0ba3\u0bae\u0bcd", remarks: "\u0b95\u0bc1\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
    cashInHand: "\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bc1\u0bb3\u0bcd\u0bb3 \u0baa\u0ba3\u0bae\u0bcd",
    totalExpense: "\u0bae\u0bca\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc6\u0bb2\u0bb5\u0bc1",
    mtgSummary: "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bae\u0bcd",
    membersPresent: "\u0bb5\u0ba8\u0bcd\u0ba4 \u0b89\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
    membersAbsent: "\u0bb5\u0bb0\u0bbe\u0ba4 \u0b89\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
    applyAll: "\u0b85\u0ba9\u0bc8\u0bb5\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b92\u0bb0\u0bc7 \u0b9a\u0bc7\u0bae\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
    apply: "\u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1",
    expenseType: "\u0b9a\u0bc6\u0bb2\u0bb5\u0bc1 \u0bb5\u0b95\u0bc8", amount: "\u0ba4\u0bca\u0b95\u0bc8",
    addExpense: "\u0b9a\u0bc6\u0bb2\u0bb5\u0bc1 \u0b9a\u0bc7\u0bb0\u0bcd",
    owner: "\u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bbf", supervisor: "\u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0bbe\u0bb0\u0bcd\u0bb5\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd",
  },
};

/** Tamil is intentionally partial; anything untranslated falls back to
 *  English so the UI never renders `undefined`. */
export function makeT(lang) {
  const base = STRINGS.en;
  const over = STRINGS[lang] || {};
  return new Proxy(
    {},
    {
      get: (_t, key) => (key in over ? over[key] : base[key]),
    }
  );
}


