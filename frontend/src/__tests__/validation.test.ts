import { describe, expect, it } from "vitest";
import { passwordProblem, validateComplaint, validateRegistration, validateVisitor } from "../lib/validation";

const good = { full_name: "Priya Sharma", email: "p@x.com", password: "Secret123", confirm: "Secret123", reg_no: "24BCE1001", phone: "9876543210", programme: "", year_of_study: "2", gender: "FEMALE" };

describe("registration validation", () => {
  it("accepts a valid form", () => expect(validateRegistration(good)).toEqual({}));
  it("rejects a bad registration number", () => expect(validateRegistration({ ...good, reg_no: "ABC" }).reg_no).toBeDefined());
  it("rejects a mismatched confirmation", () => expect(validateRegistration({ ...good, confirm: "x" }).confirm).toBeDefined());
  it("rejects an invalid phone", () => expect(validateRegistration({ ...good, phone: "12345" }).phone).toBeDefined());
  it("requires letters and digits in passwords", () => {
    expect(passwordProblem("short1")).toBeDefined();
    expect(passwordProblem("onlyletters")).toBeDefined();
    expect(passwordProblem("letters123")).toBeUndefined();
  });
});

describe("visitor validation", () => {
  const v = { visitor_name: "Rajesh Sharma", relation: "PARENT", visitor_phone: "9811122233", visit_date: "2030-01-10", time_from: "10:00", time_to: "12:00" };
  it("accepts a valid visitor", () => expect(validateVisitor(v, "2030-01-01")).toEqual({}));
  it("rejects a past date", () => expect(validateVisitor(v, "2030-02-01").visit_date).toMatch(/past/));
  it("rejects an inverted time window", () => expect(validateVisitor({ ...v, time_from: "13:00" }, "2030-01-01").time_to).toBeDefined());
});

describe("complaint validation", () => {
  it("requires category, title and description", () => {
    const e = validateComplaint({ category: "", title: "fan", description: "" });
    expect(Object.keys(e).sort()).toEqual(["category", "description", "title"]);
  });
});
