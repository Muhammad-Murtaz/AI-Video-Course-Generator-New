"use client";

import React, { ReactNode, useEffect, useState } from "react";
import axios from "axios";
import { useUser } from "@clerk/nextjs";
import { UserDetailContext } from "@/content/UserContent";

type ProviderProps = {
  children?: ReactNode;
};

function Provider(props: ProviderProps) {
  const { children } = props;
  const { user, isLoaded } = useUser(); // Use client-side hook
  const [userDetail, setUserDetail] = useState(null);

  useEffect(() => {
    const createUser = async () => {
      if (isLoaded && user) {
        try {
          const result = await axios.post("/api/user", {});
          console.log("User created:", result.data.data);
          setUserDetail(result.data.data);
        } catch (error) {
          console.error("Error creating user:", error);
        }
      }
    };

    createUser();
  }, [isLoaded, user]);

  return (
    <div className="max-w-7xl mx-auto">
      <UserDetailContext.Provider value={{}}>
        {children}
      </UserDetailContext.Provider>
    </div>
  );
}

export default Provider;
