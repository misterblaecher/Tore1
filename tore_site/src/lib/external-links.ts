const cleanEnvUrl = (value: string | undefined) => {
  const trimmed = value?.trim() ?? "";
  return trimmed.length > 0 ? trimmed : "";
};

export const WHATSAPP_URL = "https://wa.me/qr/RJBBQE34G3ALI1";
export const DISPLAY_PHONE_NUMBER = "+3249560497";

export const WAITLIST_URL = cleanEnvUrl(import.meta.env.VITE_WAITLIST_URL);
export const FEEDBACK_URL = cleanEnvUrl(import.meta.env.VITE_FEEDBACK_URL);

export const IOS_BETA_URL = cleanEnvUrl(import.meta.env.VITE_IOS_BETA_URL);
export const ANDROID_BETA_URL = cleanEnvUrl(import.meta.env.VITE_ANDROID_BETA_URL);
