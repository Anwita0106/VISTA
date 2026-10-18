export type Role = "STUDENT" | "WARDEN" | "CHIEF_WARDEN" | "STAFF" | "ADMIN";

export interface UserBrief {
  id: number;
  full_name: string;
  role: Role;
  reg_no: string | null;
}

export interface User extends UserBrief {
  email: string;
  phone: string;
  is_active: boolean;
  programme: string;
  year_of_study: number | null;
  gender: string;
  staff_type: string | null;
  hostel_id: number | null;
  hostel_name: string | null;
  room: { id: number; number: string; floor: number; block: string; block_id: number; hostel: string; room_type: string } | null;
  pref_sleep: string;
  pref_study: string;
  pref_food: string;
  looking_for_roommate: boolean;
  created_at: string;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComplaintUpdate {
  id: number;
  from_status: string | null;
  to_status: string;
  note: string;
  actor: { full_name: string } | null;
  created_at: string;
}

export interface Complaint {
  id: number;
  code: string;
  category: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  title: string;
  description: string;
  location: string;
  status: string;
  student: UserBrief;
  assigned_staff: UserBrief | null;
  escalated_to: UserBrief | null;
  escalated_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  updates?: ComplaintUpdate[];
}

export interface Visitor {
  id: number;
  visitor_name: string;
  relation: string;
  visitor_phone: string;
  visit_date: string;
  time_from: string;
  time_to: string;
  purpose: string;
  status: string;
  decision_remark: string;
  decided_by: UserBrief | null;
  decided_at: string | null;
  created_at: string;
  student: UserBrief & { room: string | null };
}

export interface ServiceRequest {
  id: number;
  kind: "SICK_MEAL" | "CLEANING";
  preferred_date: string;
  preferred_slot: string;
  meal_type: string;
  diet_notes: string;
  notes: string;
  status: string;
  assigned_staff: UserBrief | null;
  created_at: string;
  student: UserBrief & { room: string | null };
}

export interface SOSAlert {
  id: number;
  message: string;
  location: string;
  status: string;
  student: UserBrief & { phone: string; room: string | null };
  created_at: string;
  notified_at: string | null;
  notification_delay_ms: number | null;
  acknowledged_by: UserBrief | null;
  acknowledged_at: string | null;
  resolved_by: UserBrief | null;
  resolved_at: string | null;
  resolution_note: string;
}

export interface Notice {
  id: number;
  title: string;
  body: string;
  category: string;
  hostel: string;
  hostel_id: number | null;
  author: UserBrief;
  created_at: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  body: string;
  link: string;
  kind: string;
  is_read: boolean;
  created_at: string;
}

export interface FileRef {
  id: number;
  name: string;
  size: number;
  content_type: string;
  url: string;
}

export interface Delivery {
  id: number;
  code: string;
  item_description: string;
  item_type: string;
  pickup_point: string;
  fee: number;
  status: string;
  pickup_hostel: string;
  drop_hostel: string;
  sender: UserBrief;
  carrier: UserBrief | null;
  receiver: UserBrief & { room: string | null };
  payment: { amount: number; status: string; receipt_no: string; method: string } | null;
  failure_reason: string;
  created_at: string;
  accepted_at: string | null;
  picked_up_at: string | null;
  delivered_at: string | null;
  my_role: "SENDER" | "RECEIVER" | "CARRIER" | "VIEWER";
  otp_active: boolean;
  otp_expires_at: string | null;
  otp_attempts_left: number | null;
  otp?: string | null;
  qr_token?: string | null;
  verifications: { id: number; method: string; status: string; attempts: number; created_at: string; verified_at: string | null; receiver_name: string; photo: FileRef | null }[];
}

export interface GateDelivery {
  id: number;
  code: string;
  kind: "FOOD" | "PARCEL";
  vendor: string;
  courier_name: string;
  courier_phone: string;
  order_ref: string;
  expected_date: string;
  expected_time: string;
  gate: string;
  status: string;
  created_at: string;
  collected_at: string | null;
  otp_attempts: number;
  otp?: string | null;
  student: UserBrief & { room: string | null };
}

export interface Hostel {
  id: number;
  name: string;
  gender: string;
  description: string;
  blocks: { id: number; name: string; floors: number; rooms: number }[];
  capacity: number;
  occupied: number;
}

export interface Room {
  id: number;
  number: string;
  floor: number;
  capacity: number;
  room_type: string;
  block_id: number;
  block: string;
  hostel: string;
  hostel_id: number;
  occupied: number;
  occupants: { id: number; full_name: string; reg_no: string | null }[];
}
