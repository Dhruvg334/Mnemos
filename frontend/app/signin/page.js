import AuthForm from "@/components/public/AuthForm";

export const metadata = {
  title: "Sign in",
};

export default function SignInPage() {
  return <AuthForm mode="signin" />;
}
