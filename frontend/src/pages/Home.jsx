import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getToken } from "../lib/api";

export default function Home() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(getToken() ? "/dashboard" : "/login", { replace: true });
  }, [navigate]);
  return null;
}
