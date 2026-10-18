import { expect, test } from "@playwright/test";
import { actual, caseId, newUserPage, USERS } from "./helpers";

test("FT-22/FT-23/FT-24 P2P delivery end to end with OTP handover", async ({ browser }) => {
  caseId("FT-22");
  caseId("FT-23");
  caseId("FT-24");
  // sender: Rahul (Men's Hostel North) → receiver: Priya (Ladies Hostel East); carrier: Arjun
  const sender = await newUserPage(browser, USERS.rahul);
  await sender.goto("/delivery");
  await sender.getByRole("button", { name: "Send an item" }).click();
  await expect(sender.getByTestId("delivery-fee")).toHaveText("₹10");
  await sender.getByLabel("Receiver registration number").fill("24BCE1001");
  await sender.getByLabel("Item description").fill("Graphics drawing kit (E2E)");
  await sender.getByLabel(/I confirm the ₹10 delivery fee/).check();
  await sender.getByTestId("post-delivery").click();
  await expect(sender.getByTestId("delivery-status")).toContainText("Open");
  const code = (await sender.getByRole("heading", { level: 1 }).innerText()).split(" · ")[0];

  const carrier = await newUserPage(browser, USERS.arjun);
  await carrier.goto("/delivery");
  await carrier.getByRole("tab", { name: "Available to carry" }).click();
  await carrier.getByRole("link", { name: code }).click();
  await carrier.getByTestId("accept-delivery").click();
  await expect(carrier.getByTestId("delivery-status")).toContainText("Accepted");
  await carrier.getByTestId("pickup-delivery").click();
  await expect(carrier.getByTestId("delivery-status")).toContainText("Picked Up");
  await expect(carrier.getByTestId("otp-meta")).toContainText("3 attempt(s) left");

  const receiver = await newUserPage(browser, USERS.priya);
  await receiver.goto(carrier.url().replace(/^https?:\/\/[^/]+/, ""));
  const otp = (await receiver.getByTestId("receiver-otp").innerText()).trim();
  expect(otp).toMatch(/^\d{6}$/);
  await expect(receiver.getByTestId("receiver-qr")).toBeVisible();

  // one wrong attempt first, then the correct OTP
  await carrier.getByLabel("OTP").fill(otp === "000000" ? "111111" : "000000");
  await carrier.getByRole("button", { name: "Verify OTP" }).click();
  await expect(carrier.getByRole("alert").filter({ hasText: "Incorrect OTP" })).toContainText("2 attempt(s) left");
  await carrier.getByLabel("OTP").fill(otp);
  await carrier.getByRole("button", { name: "Verify OTP" }).click();
  await expect(carrier.getByTestId("delivery-status")).toContainText("Delivered");
  await sender.reload();
  await expect(sender.getByTestId("delivery-status")).toContainText("Delivered");
  await expect(sender.getByText("RCPT-DEMO-")).toBeVisible();
  actual(`UI: ${code} posted with ₹10 demo fee → accepted & picked up by carrier → receiver saw 6-digit OTP and QR → wrong OTP showed '2 attempt(s) left' → correct OTP → Delivered (also on sender's view)`);
});
