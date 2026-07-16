import AuthForm from "@/components/public/AuthForm";

export const metadata = {
  title: "Create account",
};

export default function SignUpPage() {
  return <AuthForm mode="signup" />;
}
