// Client-side validation mirrors the server rules (the server always re-validates).
export const REG_NO_RE = /^\d{2}[A-Z]{3}\d{4}$/;
export const PHONE_RE = /^[6-9]\d{9}$/;
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const NAME_RE = /^[A-Za-z .'-]{2,100}$/;

export interface RegistrationForm {
  full_name: string;
  email: string;
  password: string;
  confirm: string;
  reg_no: string;
  phone: string;
  programme: string;
  year_of_study: string;
  gender: string;
}

export function passwordProblem(pw: string): string | undefined {
  if (pw.length < 8) return "Password must be at least 8 characters";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Password must contain letters and digits";
  return undefined;
}

export function validateRegistration(f: RegistrationForm): Partial<Record<keyof RegistrationForm, string>> {
  const e: Partial<Record<keyof RegistrationForm, string>> = {};
  if (!NAME_RE.test(f.full_name.trim())) e.full_name = "Enter your full name (letters only)";
  if (!EMAIL_RE.test(f.email.trim())) e.email = "Enter a valid email address";
  if (!REG_NO_RE.test(f.reg_no.trim().toUpperCase())) e.reg_no = "Format: 24BCE1234";
  if (!PHONE_RE.test(f.phone.trim())) e.phone = "Enter a valid 10-digit mobile number";
  if (!f.gender) e.gender = "Select gender";
  const pw = passwordProblem(f.password);
  if (pw) e.password = pw;
  if (f.confirm !== f.password) e.confirm = "Passwords do not match";
  return e;
}

export function validateVisitor(v: { visitor_name: string; visitor_phone: string; visit_date: string; time_from: string; time_to: string; relation: string }, today: string) {
  const e: Record<string, string> = {};
  if (!NAME_RE.test(v.visitor_name.trim())) e.visitor_name = "Enter the visitor's name";
  if (!v.relation) e.relation = "Select the relation";
  if (!PHONE_RE.test(v.visitor_phone.trim())) e.visitor_phone = "Enter a valid 10-digit mobile number";
  if (!v.visit_date) e.visit_date = "Choose a date";
  else if (v.visit_date < today) e.visit_date = "Visit date cannot be in the past";
  if (!v.time_from || !v.time_to) e.time_to = "Choose a time window";
  else if (v.time_from >= v.time_to) e.time_to = "End time must be after start time";
  return e;
}

export function validateComplaint(c: { category: string; title: string; description: string }) {
  const e: Record<string, string> = {};
  if (!c.category) e.category = "Select a category";
  if (c.title.trim().length < 5) e.title = "Title must be at least 5 characters";
  if (c.description.trim().length < 10) e.description = "Describe the issue in at least 10 characters";
  return e;
}
