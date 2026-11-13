export type Clinic = {
  id: string;
  name: string;
  timezone: string;
  created_at: string;
};

export type Membership = {
  clinic_id: string;
  user_id: string;
  role: "owner";
};

export type MeResponse = {
  user_id: string;
  email: string | null;
  clinic: Clinic | null;
  membership: Membership | null;
};
