export type Role = {
  id: string;
  slug: string;
  name: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: Role[];
  permissions: string[];
};
