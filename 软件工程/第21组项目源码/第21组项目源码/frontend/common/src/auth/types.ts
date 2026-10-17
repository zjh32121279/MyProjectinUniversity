export type AdminUser = {
  id: number;
  admin_code: string;
  name: string;
  email: string;
  is_super_admin: boolean;
  status: string;
  permissions: string[];
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  admin: AdminUser;
};
